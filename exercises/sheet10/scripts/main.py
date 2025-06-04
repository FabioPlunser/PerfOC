#!/usr/bin/env python3

import os
import sys
from pathlib import Path
import logging
import time
import datetime
import shutil

# import argparse # No longer needed
import pandas as pd

from config import DATA_STRUCTURES, NUM_REPETITIONS
from slurm_manager import SlurmManager
from local_manager import LocalManager
from result_parser import ResultParser
from plot_generator import PlotGenerator
from markdown_generator import MarkdownGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_user_configuration():
    """Get configuration from user input via an interactive menu."""
    print("=" * 60)
    print("Data Structure Benchmark Suite")
    print("=" * 60)

    print("\nSelect Operation:")
    print("1. Run Local Benchmarks (and generate plots/markdown)")
    print("2. Run SLURM Benchmarks (and generate plots/markdown)")
    print("3. Generate Plots & Markdown from existing results")
    print("4. Generate Plots ONLY from existing results")
    print("5. Generate Markdown ONLY from existing results")
    print("6. Exit")

    config = {
        "run_benchmarks": False,
        "is_local_run": False,
        "generate_plots": False,
        "generate_markdown": False,
        "executable_path": None,
        "output_dir": None,
        "results_csv_path": None,
    }

    while True:
        choice = input("\nEnter your choice (1-6): ").strip()
        if choice == "1":  # Run Local
            config["run_benchmarks"] = True
            config["is_local_run"] = True
            config["generate_plots"] = True
            config["generate_markdown"] = True
            break
        elif choice == "2":  # Run SLURM
            config["run_benchmarks"] = True
            config["is_local_run"] = False
            config["generate_plots"] = True
            config["generate_markdown"] = True
            break
        elif choice == "3":  # Generate Plots & Markdown
            config["run_benchmarks"] = False
            config["generate_plots"] = True
            config["generate_markdown"] = True
            break
        elif choice == "4":  # Generate Plots Only
            config["run_benchmarks"] = False
            config["generate_plots"] = True
            config["generate_markdown"] = False
            break
        elif choice == "5":  # Generate Markdown Only
            config["run_benchmarks"] = False
            config["generate_plots"] = False
            config["generate_markdown"] = True
            break
        elif choice == "6":  # Exit
            logger.info("Exiting benchmark suite.")
            sys.exit(0)
        else:
            print("Invalid choice. Please enter a number between 1 and 6.")

    # Ask for output directory (common to all operational modes)
    default_output_dir = Path.cwd() / "benchmark_results"
    while True:
        output_dir_str = input(
            f"\nEnter output directory (default: {default_output_dir}): "
        ).strip()
        if not output_dir_str:
            config["output_dir"] = default_output_dir
            break
        try:
            config["output_dir"] = Path(output_dir_str)
            break
        except Exception as e:
            print(f"Invalid path for output directory: {e}")

    if config["run_benchmarks"]:
        # Ask for executable path
        default_exe_path = Path.cwd().parent / "benchmark"
        while True:
            exe_path_str = input(
                f"\nEnter path to benchmark executable ({default_exe_path}): "
            ).strip()
            if not exe_path_str or exe_path_str == default_exe_path:
                config["executable_path"] = default_exe_path
                if not config["executable_path"].exists():
                    print(f"Default executable path does not exist: {default_exe_path}")
                    print("Please enter a valid path to an executable file.")
                    continue
                break
            exe_path = Path(exe_path_str)
            if exe_path.exists() and os.access(exe_path, os.X_OK):
                config["executable_path"] = exe_path
                break
            elif not exe_path.exists():
                print(f"File not found: {exe_path}")
            else:
                print(f"File is not executable: {exe_path}")
            print("Please enter a valid path to an executable file.")
    else:
        # Ask for path to raw_results.csv
        default_csv_path = config["output_dir"] / "results" / "raw_results.csv"
        while True:
            csv_path_str = input(
                f"\nEnter path to existing raw_results.csv (default: {default_csv_path}): "
            ).strip()
            if not csv_path_str:
                config["results_csv_path"] = default_csv_path
            else:
                config["results_csv_path"] = Path(csv_path_str)

            if config["results_csv_path"].exists():
                break
            else:
                print(f"Results CSV file not found: {config['results_csv_path']}")
                print("Please enter a valid path to an existing CSV file.")
    return config


def setup_directories(
    base_dir: Path, is_local_run_mode: bool, generate_only_mode: bool
):
    """Create necessary directories. Clears some directories based on mode."""
    logger.info(
        f"Setting up directories under: {base_dir}, is_local_run_mode: {is_local_run_mode}, generate_only_mode: {generate_only_mode}"
    )

    base_dir.mkdir(parents=True, exist_ok=True)
    results_main_dir = base_dir / "results"
    results_main_dir.mkdir(parents=True, exist_ok=True)

    directories = {
        "base": base_dir,
        "results": results_main_dir,
        "plots": results_main_dir / "plots",
        "tables": results_main_dir / "tables",
    }

    # Always clear and recreate plots and tables directories for fresh output
    for dir_key in ["plots", "tables"]:
        dir_path = directories[dir_key]
        if dir_path.exists():
            logger.info(f"Clearing and recreating directory: {dir_path}")
            shutil.rmtree(dir_path)
        dir_path.mkdir(parents=True, exist_ok=True)

    if not generate_only_mode:  # If running benchmarks
        raw_csv_path = results_main_dir / "raw_results.csv"
        if raw_csv_path.exists():
            logger.info(f"Removing old raw_results.csv: {raw_csv_path}")
            raw_csv_path.unlink()

        if is_local_run_mode:
            dir_path = base_dir / "local_results"
            directories["local_results"] = dir_path
        else:  # SLURM run mode
            dir_path = base_dir / "slurm_scripts"
            directories["slurm_scripts"] = dir_path
            dir_path = base_dir / "slurm_logs"
            directories["slurm_logs"] = dir_path

        # Clear and recreate benchmark-specific directories
        for key in ["local_results", "slurm_scripts", "slurm_logs"]:
            if key in directories:
                path_to_clear = directories[key]
                if path_to_clear.exists():
                    logger.info(f"Clearing and recreating directory: {path_to_clear}")
                    shutil.rmtree(path_to_clear)
                path_to_clear.mkdir(parents=True, exist_ok=True)
    else:  # generate_only_mode is True
        # Define these keys for consistency, even if not actively cleared/created
        directories["local_results"] = base_dir / "local_results"
        directories["slurm_scripts"] = base_dir / "slurm_scripts"
        directories["slurm_logs"] = base_dir / "slurm_logs"

    logger.info(f"Directory setup complete. Working directory: {base_dir}")
    return directories


def main():
    """Main function to orchestrate the benchmark suite."""
    start_time = time.time()

    user_config = get_user_configuration()

    output_dir = user_config["output_dir"]
    run_benchmarks_mode = user_config["run_benchmarks"]
    generate_only_mode = not run_benchmarks_mode
    is_local_run_config = user_config["is_local_run"]
    executable_path = user_config["executable_path"]
    results_csv_path_input = user_config["results_csv_path"]

    should_generate_plots = user_config["generate_plots"]
    should_generate_markdown = user_config["generate_markdown"]

    directories = setup_directories(
        output_dir,
        is_local_run_mode=is_local_run_config,
        generate_only_mode=generate_only_mode,
    )

    result_parser = ResultParser()
    plot_generator = PlotGenerator(directories["plots"])
    markdown_generator = MarkdownGenerator(directories["tables"])

    results_df = pd.DataFrame()
    benchmarks_were_run_this_session = False

    if run_benchmarks_mode:
        benchmarks_were_run_this_session = True
        logger.info("Starting comprehensive data structure benchmark suite")

        if is_local_run_config:
            try:
                local_manager = LocalManager(
                    directories["local_results"], executable_path
                )
                local_results_raw = local_manager.run_all_benchmarks()
                if local_results_raw:
                    results_df = result_parser.collect_local_results(local_results_raw)
                else:
                    logger.error("Local benchmarks ran but produced no raw results.")
            except Exception as e:
                logger.error(f"Local benchmarking failed: {e}", exc_info=True)
                sys.exit(1)
        else:  # SLURM benchmarking
            try:
                slurm_manager = SlurmManager(
                    directories["slurm_scripts"],
                    directories["slurm_logs"],
                    executable_path,
                )
                combinations = slurm_manager.generate_combinations()
                if not combinations:
                    logger.error("No SLURM combinations generated.")
                    sys.exit(1)

                logger.info(f"Total SLURM combinations: {len(combinations)}")
                logger.info(f"Total SLURM jobs: {len(combinations) * NUM_REPETITIONS}")

                job_ids = slurm_manager.submit_all_jobs(combinations)
                if not job_ids:
                    logger.error("No SLURM jobs were submitted successfully")
                    sys.exit(1)

                slurm_manager.wait_for_jobs(job_ids)
                logger.info("Collecting SLURM results...")
                results_df = result_parser.collect_all_results(
                    combinations, directories["slurm_logs"]
                )
            except Exception as e:
                logger.error(f"SLURM benchmarking failed: {e}", exc_info=True)
                sys.exit(1)
    elif generate_only_mode:  # Load existing results
        logger.info(
            f"Loading results from {results_csv_path_input} for report/plot generation."
        )
        try:
            results_df = pd.read_csv(results_csv_path_input)
            if results_df.empty:
                logger.warning(
                    f"The provided results file {results_csv_path_input} is empty."
                )
        except Exception as e:
            logger.error(f"Failed to load or parse {results_csv_path_input}: {e}")
            sys.exit(1)

    # --- Analysis and Generation ---
    if not results_df.empty:
        if (
            benchmarks_were_run_this_session
        ):  # Save raw results if benchmarks were just run
            raw_results_output_path = directories["results"] / "raw_results.csv"
            results_df.to_csv(raw_results_output_path, index=False)
            logger.info(
                f"Raw results from benchmark run saved to {raw_results_output_path}"
            )

        if should_generate_plots:
            logger.info("Generating plots...")
            plot_generator.create_all_plots(results_df)
        else:
            logger.info("Skipping plot generation as per user choice.")

        if should_generate_markdown:
            logger.info("Generating markdown report...")
            markdown_generator.generate_full_report(results_df)
        else:
            logger.info("Skipping markdown report generation as per user choice.")

        if benchmarks_were_run_this_session:
            logger.info("\n" + "=" * 50)
            logger.info("BENCHMARK RUN SUMMARY")
            logger.info("=" * 50)
            if "error" in results_df.columns:
                successful_runs_df = results_df[
                    results_df["ops_per_second"].notna()
                    & (results_df["error"] != True)
                    & (
                        results_df["error"].isna()
                        if "error" in results_df.columns
                        else True
                    )
                ]  # More robust check
                num_successful = len(successful_runs_df)
                num_failed = len(results_df) - num_successful
            else:
                successful_runs_df = results_df[results_df["ops_per_second"].notna()]
                num_successful = len(successful_runs_df)
                num_failed = len(results_df) - num_successful

            logger.info(f"Total benchmark configurations processed: {len(results_df)}")
            logger.info(f"Successfully parsed runs with metrics: {num_successful}")
            logger.info(
                f"Failed/Incomplete runs (no metrics or error reported): {num_failed}"
            )

            if num_successful > 0 and "ops_per_second" in successful_runs_df.columns:
                fastest = successful_runs_df.loc[
                    successful_runs_df["ops_per_second"].idxmax()
                ]
                logger.info(
                    f"\nFastest among successful: {fastest['container']} "
                    f"({fastest['ops_per_second']:.0f} ops/sec)"
                )
    elif generate_only_mode:
        logger.error(
            f"No data loaded from {results_csv_path_input}, cannot generate plots or markdown."
        )
    else:  # Benchmarks were run, but results_df is empty
        logger.error("No results collected or parsed from the benchmark run!")

    end_time = time.time()
    total_time_seconds = end_time - start_time
    total_time_delta = datetime.timedelta(seconds=total_time_seconds)
    logger.info(f"\nTotal script execution time: {total_time_delta}")
    logger.info(f"All outputs are located in subdirectories of: {output_dir.resolve()}")


if __name__ == "__main__":
    main()
