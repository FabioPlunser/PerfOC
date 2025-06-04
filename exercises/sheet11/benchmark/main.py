import os
import subprocess
import logging
from pathlib import Path
import pandas as pd

import config
import slurm_manager
import results_parser
import plot_generator
import markdown_generator

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def compile_c_programs():
    """Compiles all C programs defined in config."""
    logger.info("Compiling C programs...")
    compiled_executables = {}

    for prog_name in config.PROGRAMS:
        source_file = config.C_SOURCE_DIR / f"{prog_name}.c"
        time_source_file = config.C_SOURCE_DIR / "timing.c"
        executable_file = config.BIN_DIR / prog_name

        if not source_file.exists():
            logger.error(f"Source file {source_file} not found for {prog_name}.")
            continue
        compile_cmd = [
            "gcc",
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-O3",
            str(source_file),
            str(time_source_file),
            "-o",
            str(executable_file),
        ]
        logger.info(f"Compiling {prog_name}: {' '.join(compile_cmd)}")
        try:
            result = subprocess.run(
                compile_cmd, capture_output=True, text=True, check=True
            )
            logger.info(f"Successfully compiled {prog_name} to {executable_file}")
            logger.debug(f"Compiler output: {result.stdout}")
            compiled_executables[prog_name] = executable_file.resolve()
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to compile {prog_name}:\n{e.stderr}")
        except FileNotFoundError:
            logger.error("GCC not found. Please ensure it's installed and in PATH.")
            return None  

    if not compiled_executables:
        logger.error("No programs were successfully compiled. Exiting.")
        return None
    return compiled_executables


def generate_and_submit_jobs(compiled_executables: dict):
    """Generates SLURM scripts and submits them."""
    all_job_ids = []
    job_details_for_parsing = []  

    for prog_name, exec_path in compiled_executables.items():
        n_values_for_this_program = config.PROGRAM_N_VALUES.get(prog_name)
        if not n_values_for_this_program:
            logger.warning(
                f"No N_VALUES defined for program '{prog_name}' in "
                f"config.PROGRAM_N_VALUES. Skipping this program."
            )
            continue # Skip to the next program if no N values are defined

        logger.info(f"Using N values for {prog_name}: {n_values_for_this_program}")
        for n_val in n_values_for_this_program:
            for rep in range(1, config.NUM_REPETITIONS + 1):
                job_name = f"{prog_name}_N{n_val}_rep{rep}"
                script_path = slurm_manager.create_slurm_script(
                    prog_name, n_val, rep, exec_path, job_name
                )
                job_id = slurm_manager.submit_slurm_job(script_path)
                if job_id:
                    all_job_ids.append(job_id)
                    log_file_name = f"{job_name}.out"
                    job_details_for_parsing.append(
                        (prog_name, n_val, rep, log_file_name)
                    )

    if not all_job_ids:
        logger.error("No SLURM jobs were submitted. Check compilation and SLURM setup.")
        return [], []

    return all_job_ids, job_details_for_parsing


def collect_all_results(job_details: list):
    """Parses all SLURM log files."""
    all_parsed_data = []
    logger.info(f"Attempting to parse {len(job_details)} log files...")

    for prog_name, n_val, rep, log_file_name in job_details:
        log_path = config.SLURM_LOGS_DIR / log_file_name
        parsed_data = results_parser.parse_single_log(log_path, prog_name, n_val, rep)
        if parsed_data:
            all_parsed_data.append(parsed_data)
        else:  
            all_parsed_data.append(
                {
                    "program": prog_name,
                    "n_value": n_val,
                    "repetition": rep,
                    "log_file": log_file_name,
                    "error_detected": True,
                    "parse_error": "Log file not found or critical parse failure",
                }
            )

    if not all_parsed_data:
        logger.warning("No results were parsed. Check SLURM logs and parsing logic.")
        return pd.DataFrame()

    return pd.DataFrame(all_parsed_data)

def clear_previous_results():
    """Clears all folders"""
    logger.info("Clearing previous results and logs...")
    for folder in [
        config.BIN_DIR,
        config.SLURM_SCRIPTS_DIR,
        config.SLURM_LOGS_DIR,
        config.PLOTS_DIR,
        config.TABLES_DIR,
    ]:
        if folder.exists():
            for item in folder.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    for sub_item in item.iterdir():
                        sub_item.unlink()
                    item.rmdir()
            logger.info(f"Cleared contents of {folder}")
        else:
            logger.info(f"{folder} does not exist, skipping.")

def generate_folders():
    """Ensures all necessary directories exist."""
    config.BIN_DIR.mkdir(parents=True, exist_ok=True)
    config.SLURM_SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    config.SLURM_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    config.RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    config.PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    config.TABLES_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("All necessary directories are ready.")

def print_config():
    """Prints the current configuration settings."""
    print("Current Configuration:")
    print(f"Programs: {config.PROGRAMS}")
    print(f"N Values: {config.PROGRAM_N_VALUES}")
    print(f"SLURM Partition: {config.SLURM_PARTITION}")
    print(f"SLURM CPUs per Task: {config.SLURM_CPUS_PER_TASK}")
    print(f"SLURM Memory: {config.SLURM_MEMORY}")
    print(f"SLURM Time Limit: {config.SLURM_TIME_LIMIT}")
    print(f"Number of Repetitions: {config.NUM_REPETITIONS}")
    print(f"Plot Format: {config.PLOT_FORMAT}")
    print(f"Plot DPI: {config.PLOT_DPI}")
    print(f"Plot Style: {config.PLOT_STYLE}")
    print(f"Base Output Directory: {config.BASE_OUTPUT_DIR}")
    
def check_for_input(): 
    """Check if user provides input to do the benchmark, the plots and the markdown report."""
    print("=" * 60)
    print("Dellanoy Benchmark")
    print("=" * 60)

    print_config()
    
    print("\nSelect Operation:")
    print("1. Run Benchmark")
    print("2. Generate Plots")
    print("3. Generate Markdown Report")
    print("5. Exit")
    print("=" * 60)

    while True:
        choice = input("Enter your choice (1-5): ").strip()
        if choice in {'1', '2', '3', '4', '5'}:
            return choice
        else:
            print("Invalid choice. Please enter a number between 1 and 5.") 
            
    
def main():
    logger.info("Starting Delannoy Benchmark Suite...")
    
    user_choice = check_for_input()
    if user_choice == '5':
        logger.info("Exiting without running any operations.")
        return
    elif user_choice == '2':
        logger.info("Generating plots only...")
        results_df = pd.read_csv(config.RESULTS_FILE)
        if results_df.empty:
            logger.error("No results found to generate plots. Please run the benchmark first.")
            return
        plot_generator.generate_all_plots(results_df)
        logger.info("Plots generated successfully.")
        return
    elif user_choice == '3':
        logger.info("Generating markdown report only...")
        results_df = pd.read_csv(config.RESULTS_FILE)
        if results_df.empty:
            logger.error("No results found to generate markdown report. Please run the benchmark first.")
            return
        markdown_generator.save_markdown_report(results_df)
        logger.info("Markdown report generated successfully.")
        return
    elif user_choice == '1':
        logger.info("Running all operations: Benchmark, Plots, and Markdown Report.")

        clear_previous_results()
        generate_folders()
        logger.info("Directories cleared and created as needed.")

        compiled_executables = compile_c_programs()
        if not compiled_executables:
            logger.error("Compilation failed. Exiting.")
            return

        logger.info("Proceeding to generate and submit SLURM jobs.")
        job_ids, job_details_for_parsing = generate_and_submit_jobs(compiled_executables)

        if not job_ids:
            logger.error("No jobs submitted or all submissions failed. Exiting.")
            return

        slurm_manager.wait_for_slurm_jobs(job_ids)
        logger.info("All SLURM jobs presumed complete. Proceeding to parse results.")

        results_df = collect_all_results(job_details_for_parsing)

        if results_df.empty:
            logger.error("No data collected after parsing. Check logs and parser.")
        else:
            logger.info(f"Successfully parsed {len(results_df)} results.")
            results_df.to_csv(config.RESULTS_FILE, index=False)
            logger.info(f"Raw results saved to {config.RESULTS_FILE}")

            # Generate plots and markdown report
            plot_generator.generate_all_plots(results_df)
            markdown_generator.save_markdown_report(results_df)

        logger.info("Delannoy Benchmark Suite finished.")


if __name__ == "__main__":
    # Create directories from config if they don't exist (already in config.py)
    # config.BIN_DIR.mkdir(parents=True, exist_ok=True)
    # config.SLURM_SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    # config.SLURM_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    # config.RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    # config.PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    # config.TABLES_DIR.mkdir(parents=True, exist_ok=True)
    main()
