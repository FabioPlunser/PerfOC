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
        for n_val in config.N_VALUES:
            if prog_name == "delannoy" and n_val > 18:  
                logger.warning(
                    f"Skipping {prog_name} for N={n_val} in SLURM submission "
                    f"as it might be too slow. It will likely timeout. "
                    f"Consider adjusting N_VALUES or SLURM_TIME_LIMIT if you want to run it."
                )

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


def main():
    logger.info("Starting Delannoy Benchmark Suite...")

    compiled_executables = compile_c_programs()
    if not compiled_executables:
        logger.error("Compilation failed. Exiting.")
        return

    # --- Option to load existing results or run new benchmarks ---
    # For simplicity, this script will always try to run new benchmarks.
    # You could add a check here for config.RESULTS_FILE.exists() to load instead.

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
