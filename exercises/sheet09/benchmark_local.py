#!/usr/bin/env python3

import os
import sys
import subprocess
import itertools
import time
import datetime
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import logging
import json
import platform
import psutil
import resource

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("local_benchmark_runner.log"),
    ],
)
logger = logging.getLogger(__name__)

# Configuration for local benchmarks
LOCAL_BENCHMARK_EXECUTABLE = "./benchmark"  # Adjust path as needed
NUM_REPETITIONS = 3
TIMEOUT_SECONDS = 30  # 5 minutes per benchmark

# Benchmark parameters (same as cluster version)
DATA_STRUCTURES = ["array", "list_seq", "list_rand"]
INSTRUCTION_MIXES = [
    {"ins_del": 0.0, "read_write": 1.0},
    {"ins_del": 0.01, "read_write": 0.99},
    {"ins_del": 0.10, "read_write": 0.90},
    {"ins_del": 0.50, "read_write": 0.50},
]
ELEMENT_SIZES = [8, 512, 8 * 1024 * 1024]  # 8 Byte, 512 Byte, 8 MB
NUM_ELEMENTS = [10, 1000, 100000, 10000000]

# Local directories
LOCAL_RESULTS_DIR = Path("./local_benchmark_results")
LOCAL_LOGS_DIR = LOCAL_RESULTS_DIR / "logs"
LOCAL_PLOTS_DIR = LOCAL_RESULTS_DIR / "plots"
LOCAL_TABLES_DIR = LOCAL_RESULTS_DIR / "tables"


def setup_local_directories():
    """Create necessary directories for local benchmarks."""
    for directory in [
        LOCAL_RESULTS_DIR,
        LOCAL_LOGS_DIR,
        LOCAL_PLOTS_DIR,
        LOCAL_TABLES_DIR,
    ]:
        directory.mkdir(parents=True, exist_ok=True)
    logger.info(f"Local benchmark directory: {LOCAL_RESULTS_DIR}")


def get_system_info():
    """Collect system information for the benchmark report."""
    info = {
        "platform": platform.platform(),
        "system": platform.system(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "cpu_count": psutil.cpu_count(logical=False),
        "cpu_count_logical": psutil.cpu_count(logical=True),
        "memory_total_gb": psutil.virtual_memory().total / (1024**3),
        "timestamp": datetime.datetime.now().isoformat(),
    }

    # Try to get CPU frequency
    try:
        cpu_freq = psutil.cpu_freq()
        if cpu_freq:
            info["cpu_freq_max_mhz"] = cpu_freq.max
            info["cpu_freq_current_mhz"] = cpu_freq.current
    except:
        pass

    # Try to get more detailed CPU info on macOS
    if platform.system() == "Darwin":
        try:
            result = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True,
                check=True,
            )
            info["cpu_model"] = result.stdout.strip()
        except:
            pass

        try:
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True,
                text=True,
                check=True,
            )
            info["memory_total_bytes"] = int(result.stdout.strip())
        except:
            pass

    return info


def estimate_local_memory_usage(num_elements, element_size):
    """Estimate memory usage for local system (more conservative)."""
    # Base memory for the data structure
    base_memory = num_elements * element_size / (1024 * 1024)  # MB

    # Overhead for linked lists
    if element_size <= 8:
        overhead_factor = 3.0  # Conservative for small elements
    else:
        overhead_factor = 1.5

    # Growth during benchmark
    growth_factor = 1.5

    total_memory = base_memory * overhead_factor * growth_factor
    total_memory += 50  # 50MB base overhead

    return total_memory


def should_exclude_local_combination(ds, num_elements, element_size):
    """Determine if a combination should be excluded for local execution."""
    # memory_mb = estimate_local_memory_usage(num_elements, element_size) available_memory_gb = psutil.virtual_memory().available / (1024**3)

    # Exclude if estimated memory > 50% of available memory
    # if memory_mb > (available_memory_gb * 1024 * 0.5):
    #     logger.info(
    #         f"Excluding {ds} with {num_elements} elements of {element_size} bytes "
    #         f"(estimated {memory_mb:.1f} MB, available {available_memory_gb:.1f} GB)"
    #     )
    #     return True

    # Exclude very large linked lists (too slow for local testing)
    if ds.startswith("list") and num_elements >= 1000000 and element_size >= 512:
        logger.info(
            f"Excluding slow combination: {ds} with {num_elements} elements of {element_size} bytes"
        )
        return True

    # Exclude extremely large arrays
    if ds == "array" and num_elements >= 10000000 and element_size >= 512:
        logger.info(f"Excluding large array combination: {ds}")
        return True

    return False


def generate_local_benchmark_combinations():
    """Generate all valid benchmark parameter combinations for local execution."""
    combinations = []
    excluded_count = 0

    for ds, mix, num_elem, elem_size in itertools.product(
        DATA_STRUCTURES, INSTRUCTION_MIXES, NUM_ELEMENTS, ELEMENT_SIZES
    ):
        if should_exclude_local_combination(ds, num_elem, elem_size):
            excluded_count += 1
            continue

        combinations.append(
            {
                "data_structure": ds,
                "num_elements": num_elem,
                "element_size": elem_size,
                "ins_del_ratio": mix["ins_del"],
                "read_write_ratio": mix["read_write"],
                "estimated_memory_mb": estimate_local_memory_usage(num_elem, elem_size),
            }
        )

    logger.info(
        f"Generated {len(combinations)} valid local combinations, excluded {excluded_count}"
    )
    return combinations


def run_single_benchmark(combination, run_id):
    """Run a single benchmark and return the results."""
    logger.info(
        f"Running: {combination['data_structure']} "
        f"n={combination['num_elements']} "
        f"size={combination['element_size']} "
        f"ins/del={combination['ins_del_ratio']} "
        f"run={run_id}"
    )

    # Prepare command
    cmd = [
        LOCAL_BENCHMARK_EXECUTABLE,
        combination["data_structure"],
        str(combination["num_elements"]),
        str(combination["read_write_ratio"]),
        str(combination["ins_del_ratio"]),
    ]

    # Create log file for this run
    log_filename = (
        f"{combination['data_structure']}_"
        f"{combination['num_elements']}_"
        f"{combination['element_size']}_"
        f"{combination['ins_del_ratio']}_"
        f"run{run_id}.log"
    )
    log_path = LOCAL_LOGS_DIR / log_filename

    try:
        # Record resource usage before
        process = psutil.Process()
        start_memory = process.memory_info().rss / (1024 * 1024)  # MB

        # Run benchmark with timeout
        start_time = time.time()
        start_cpu_time = time.process_time()

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            cwd=Path(LOCAL_BENCHMARK_EXECUTABLE).parent,
        )

        end_time = time.time()
        end_cpu_time = time.process_time()

        # Record resource usage after
        end_memory = process.memory_info().rss / (1024 * 1024)  # MB

        # Save log
        with open(log_path, "w") as f:
            f.write(f"Command: {' '.join(cmd)}\n")
            f.write(f"Return code: {result.returncode}\n")
            f.write(f"Wall time: {end_time - start_time:.6f} seconds\n")
            f.write(f"CPU time: {end_cpu_time - start_cpu_time:.6f} seconds\n")
            f.write(f"Memory before: {start_memory:.2f} MB\n")
            f.write(f"Memory after: {end_memory:.2f} MB\n")
            f.write(f"Memory delta: {end_memory - start_memory:.2f} MB\n")
            f.write("=" * 50 + "\n")
            f.write("STDOUT:\n")
            f.write(result.stdout)
            f.write("\n" + "=" * 50 + "\n")
            f.write("STDERR:\n")
            f.write(result.stderr)

        if result.returncode == 0:
            # Parse benchmark output
            data = combination.copy()
            data.update(
                {
                    "run_id": run_id,
                    "platform": "local_macos",
                    "wall_time_s": end_time - start_time,
                    "cpu_time_s": end_cpu_time - start_cpu_time,
                    "memory_delta_mb": end_memory - start_memory,
                    "log_file": str(log_path),
                    "error": False,
                }
            )

            # Parse benchmark-specific output
            import re

            content = result.stdout

            # Total Time: 0.123456 seconds
            time_match = re.search(r"Total Time: ([\d\.]+) seconds", content)
            if time_match:
                data["total_time_s"] = float(time_match.group(1))

            # Operations Completed: 1000000
            ops_match = re.search(r"Operations Completed: (\d+)", content)
            if ops_match:
                data["operations_completed"] = int(ops_match.group(1))

            # Operations per Second: 1234567.89
            ops_per_sec_match = re.search(r"Operations per Second: ([\d\.]+)", content)
            if ops_per_sec_match:
                data["ops_per_second"] = float(ops_per_sec_match.group(1))

            # Cycles per Operation: 123
            cycles_match = re.search(r"Cycles per Operation: (\d+)", content)
            if cycles_match:
                data["cycles_per_op"] = int(cycles_match.group(1))

            # Checksum
            checksum_match = re.search(r"Checksum: (\d+)", content)
            if checksum_match:
                data["checksum"] = int(checksum_match.group(1))

            logger.info(
                f"  ✓ Completed in {data['wall_time_s']:.3f}s, "
                f"{data.get('ops_per_second', 0):.0f} ops/sec"
            )
            return data
        else:
            logger.error(f"  ✗ Benchmark failed with return code {result.returncode}")
            return {
                **combination,
                "run_id": run_id,
                "platform": "local_macos",
                "error": True,
                "error_code": result.returncode,
                "log_file": str(log_path),
            }

    except subprocess.TimeoutExpired:
        logger.warning(f"  ⏰ Benchmark timed out after {TIMEOUT_SECONDS}s")
        return {
            **combination,
            "run_id": run_id,
            "platform": "local_macos",
            "error": True,
            "error_type": "timeout",
            "log_file": str(log_path),
        }
    except Exception as e:
        logger.error(f"  ✗ Benchmark failed with exception: {e}")
        return {
            **combination,
            "run_id": run_id,
            "platform": "local_macos",
            "error": True,
            "error_type": "exception",
            "error_message": str(e),
            "log_file": str(log_path),
        }


def run_all_local_benchmarks():
    """Run all local benchmarks sequentially."""
    logger.info("Starting comprehensive local benchmark suite")

    # Check if benchmark executable exists
    if not os.path.exists(LOCAL_BENCHMARK_EXECUTABLE):
        logger.error(f"Benchmark executable not found at {LOCAL_BENCHMARK_EXECUTABLE}")
        return None

    # Make sure it's executable
    os.chmod(LOCAL_BENCHMARK_EXECUTABLE, 0o755)

    # Generate combinations
    combinations = generate_local_benchmark_combinations()

    # Save combinations for reference
    with open(LOCAL_RESULTS_DIR / "combinations.json", "w") as f:
        json.dump(combinations, f, indent=2)

    # Save system info
    system_info = get_system_info()
    with open(LOCAL_RESULTS_DIR / "system_info.json", "w") as f:
        json.dump(system_info, f, indent=2)

    logger.info(f"System: {system_info['platform']}")
    logger.info(f"CPU: {system_info.get('cpu_model', 'Unknown')}")
    logger.info(f"Memory: {system_info['memory_total_gb']:.1f} GB")
    logger.info(f"Total combinations: {len(combinations)}")
    logger.info(f"Total runs: {len(combinations) * NUM_REPETITIONS}")

    # Run all benchmarks
    all_results = []
    total_runs = len(combinations) * NUM_REPETITIONS
    current_run = 0

    start_time = time.time()

    for i, combination in enumerate(combinations):
        logger.info(
            f"\nCombination {i+1}/{len(combinations)}: "
            f"{combination['data_structure']} "
            f"n={combination['num_elements']} "
            f"size={combination['element_size']}B"
        )

        for run_id in range(1, NUM_REPETITIONS + 1):
            current_run += 1
            elapsed = time.time() - start_time
            if current_run > 1:
                eta = elapsed * (total_runs / current_run - 1)
                logger.info(
                    f"Progress: {current_run}/{total_runs} "
                    f"({100*current_run/total_runs:.1f}%) "
                    f"ETA: {datetime.timedelta(seconds=int(eta))}"
                )

            result = run_single_benchmark(combination, run_id)
            if result:
                all_results.append(result)

                # Save intermediate results every 10 runs
                if current_run % 10 == 0:
                    df = pd.DataFrame(all_results)
                    df.to_csv(
                        LOCAL_RESULTS_DIR / "intermediate_results.csv", index=False
                    )

    # Save final results
    if all_results:
        df = pd.DataFrame(all_results)
        df.to_csv(LOCAL_RESULTS_DIR / "raw_results.csv", index=False)

        # Save successful runs separately
        success_df = df[~df.get("error", True)]
        if not success_df.empty:
            success_df.to_csv(LOCAL_RESULTS_DIR / "successful_results.csv", index=False)

        logger.info(f"\nBenchmark suite completed!")
        logger.info(f"Total runs: {len(df)}")
        logger.info(f"Successful runs: {len(success_df)}")
        logger.info(f"Failed runs: {len(df) - len(success_df)}")
        logger.info(
            f"Total time: {datetime.timedelta(seconds=int(time.time() - start_time))}"
        )

        return df
    else:
        logger.error("No results collected!")
        return None


def create_local_summary_tables(df):
    """Create summary tables for local results."""
    if df.empty:
        logger.warning("No data to create tables")
        return

    success_df = df[~df.get("error", True)].copy()

    if success_df.empty:
        logger.warning("No successful runs to analyze")
        return

    # Group by configuration and calculate statistics
    group_cols = [
        "data_structure",
        "num_elements",
        "element_size",
        "ins_del_ratio",
        "read_write_ratio",
    ]

    summary = (
        success_df.groupby(group_cols)
        .agg(
            {
                "total_time_s": ["mean", "std", "min", "max"],
                "ops_per_second": ["mean", "std", "min", "max"],
                "wall_time_s": ["mean", "std", "min", "max"],
                "cpu_time_s": ["mean", "std", "min", "max"],
                "memory_delta_mb": ["mean", "std", "min", "max"],
            }
        )
        .round(4)
    )

    # Flatten column names
    summary.columns = [f"{col[1]}_{col[0]}" for col in summary.columns]
    summary = summary.reset_index()

    # Save detailed summary
    summary.to_csv(LOCAL_TABLES_DIR / "detailed_summary.csv", index=False)

    # Create markdown summary
    with open(LOCAL_TABLES_DIR / "summary.md", "w") as f:
        f.write("# Local Benchmark Results Summary\n\n")

        # System info
        try:
            with open(LOCAL_RESULTS_DIR / "system_info.json", "r") as sys_file:
                system_info = json.load(sys_file)
            f.write("## System Information\n\n")
            f.write(f"- **Platform**: {system_info['platform']}\n")
            f.write(f"- **CPU**: {system_info.get('cpu_model', 'Unknown')}\n")
            f.write(
                f"- **CPU Cores**: {system_info['cpu_count']} physical, {system_info['cpu_count_logical']} logical\n"
            )
            f.write(f"- **Memory**: {system_info['memory_total_gb']:.1f} GB\n")
            f.write(f"- **Timestamp**: {system_info['timestamp']}\n\n")
        except:
            pass

        f.write("## Performance Overview\n\n")
        f.write(summary.to_markdown(index=False))
        f.write("\n\n")

        # Performance comparison
        f.write("## Performance Comparison (Operations per Second)\n\n")
        perf_pivot = success_df.pivot_table(
            values="ops_per_second",
            index=["num_elements", "element_size"],
            columns="data_structure",
            aggfunc="mean",
        ).round(0)
        f.write(perf_pivot.to_markdown())
        f.write("\n\n")

        # Memory usage
        f.write("## Memory Usage (MB)\n\n")
        mem_pivot = success_df.pivot_table(
            values="memory_delta_mb",
            index=["num_elements", "element_size"],
            columns="data_structure",
            aggfunc="mean",
        ).round(2)
        f.write(mem_pivot.to_markdown())

    logger.info(f"Summary tables saved to {LOCAL_TABLES_DIR}")


def create_local_plots(df):
    """Create comprehensive plots for local results."""
    if df.empty:
        logger.warning("No data to plot")
        return

    success_df = df[~df.get("error", True)].copy()

    if success_df.empty:
        logger.warning("No successful runs to plot")
        return

    # Set up plotting style
    plt.style.use("default")
    sns.set_palette("husl")

    # 1. Performance overview
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle("Local Data Structure Performance Analysis", fontsize=16)

    # Operations per second vs number of elements
    ax1 = axes[0, 0]
    for ds in success_df["data_structure"].unique():
        ds_data = success_df[success_df["data_structure"] == ds]
        grouped = ds_data.groupby("num_elements")["ops_per_second"].mean()
        ax1.loglog(grouped.index, grouped.values, marker="o", label=ds, linewidth=2)
    ax1.set_xlabel("Number of Elements")
    ax1.set_ylabel("Operations per Second")
    ax1.set_title("Performance vs Data Structure Size")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Memory usage vs number of elements
    ax2 = axes[0, 1]
    for ds in success_df["data_structure"].unique():
        ds_data = success_df[success_df["data_structure"] == ds]
        grouped = ds_data.groupby("num_elements")["memory_delta_mb"].mean()
        ax2.loglog(grouped.index, grouped.values, marker="s", label=ds, linewidth=2)
    ax2.set_xlabel("Number of Elements")
    ax2.set_ylabel("Memory Usage (MB)")
    ax2.set_title("Memory Usage vs Data Structure Size")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    # Performance vs element size
    ax3 = axes[1, 0]
    for ds in success_df["data_structure"].unique():
        ds_data = success_df[success_df["data_structure"] == ds]
        grouped = ds_data.groupby("element_size")["ops_per_second"].mean()
        ax3.semilogx(grouped.index, grouped.values, marker="^", label=ds, linewidth=2)
    ax3.set_xlabel("Element Size (Bytes)")
    ax3.set_ylabel("Operations per Second")
    ax3.set_title("Performance vs Element Size")
    ax3.legend()
    ax3.grid(True, alpha=0.3)

    # Performance vs instruction mix
    ax4 = axes[1, 1]
    for ds in success_df["data_structure"].unique():
        ds_data = success_df[success_df["data_structure"] == ds]
        grouped = ds_data.groupby("ins_del_ratio")["ops_per_second"].mean()
        ax4.plot(grouped.index * 100, grouped.values, marker="d", label=ds, linewidth=2)
    ax4.set_xlabel("Insert/Delete Ratio (%)")
    ax4.set_ylabel("Operations per Second")
    ax4.set_title("Performance vs Instruction Mix")
    ax4.legend()
    ax4.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(
        LOCAL_PLOTS_DIR / "performance_overview.png", dpi=300, bbox_inches="tight"
    )
    plt.close()

    # 2. Performance heatmaps
    fig, axes = plt.subplots(1, 3, figsize=(20, 6))

    for i, ds in enumerate(["array", "list_seq", "list_rand"]):
        if ds not in success_df["data_structure"].values:
            continue

        ds_data = success_df[success_df["data_structure"] == ds]
        pivot_data = ds_data.pivot_table(
            values="ops_per_second",
            index="num_elements",
            columns="element_size",
            aggfunc="mean",
        )

        if not pivot_data.empty:
            sns.heatmap(
                np.log10(pivot_data),
                annot=True,
                fmt=".1f",
                cmap="viridis",
                ax=axes[i],
                cbar_kws={"label": "log10(Ops/sec)"},
            )
            axes[i].set_title(f'{ds.replace("_", " ").title()} Performance')
            axes[i].set_xlabel("Element Size (Bytes)")
            axes[i].set_ylabel("Number of Elements")

    plt.tight_layout()
    plt.savefig(
        LOCAL_PLOTS_DIR / "performance_heatmaps.png", dpi=300, bbox_inches="tight"
    )
    plt.close()

    # 3. Box plots for variability
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))

    # Performance variability
    sns.boxplot(data=success_df, x="data_structure", y="ops_per_second", ax=axes[0, 0])
    axes[0, 0].set_yscale("log")
    axes[0, 0].set_title("Performance Variability by Data Structure")
    axes[0, 0].tick_params(axis="x", rotation=45)

    # Wall time vs CPU time
    sns.scatterplot(
        data=success_df,
        x="cpu_time_s",
        y="wall_time_s",
        hue="data_structure",
        ax=axes[0, 1],
    )
    axes[0, 1].set_xlabel("CPU Time (s)")
    axes[0, 1].set_ylabel("Wall Time (s)")
    axes[0, 1].set_title("CPU Time vs Wall Time")

    # Memory usage by data structure
    sns.boxplot(data=success_df, x="data_structure", y="memory_delta_mb", ax=axes[1, 0])
    axes[1, 0].set_title("Memory Usage by Data Structure")
    axes[1, 0].tick_params(axis="x", rotation=45)

    # Performance by instruction mix
    sns.boxplot(
        data=success_df,
        x="ins_del_ratio",
        y="ops_per_second",
        hue="data_structure",
        ax=axes[1, 1],
    )
    axes[1, 1].set_yscale("log")
    axes[1, 1].set_title("Performance by Instruction Mix")

    plt.tight_layout()
    plt.savefig(
        LOCAL_PLOTS_DIR / "variability_analysis.png", dpi=300, bbox_inches="tight"
    )
    plt.close()

    logger.info(f"Plots saved to {LOCAL_PLOTS_DIR}")


def main():
    """Main function for local benchmark execution."""
    logger.info("=" * 60)
    logger.info("LOCAL BENCHMARK RUNNER")
    logger.info("=" * 60)

    setup_local_directories()

    # Run all benchmarks
    results_df = run_all_local_benchmarks()

    if results_df is not None and not results_df.empty:
        # Create analysis
        create_local_summary_tables(results_df)
        create_local_plots(results_df)

        # Print final summary
        success_df = results_df[~results_df.get("error", True)]

        logger.info("\n" + "=" * 50)
        logger.info("FINAL SUMMARY")
        logger.info("=" * 50)
        logger.info(f"Total runs: {len(results_df)}")
        logger.info(f"Successful runs: {len(success_df)}")
        logger.info(f"Failed runs: {len(results_df) - len(success_df)}")

        if not success_df.empty:
            fastest = success_df.loc[success_df["ops_per_second"].idxmax()]
            slowest = success_df.loc[success_df["ops_per_second"].idxmin()]

            logger.info(f"\nFastest configuration:")
            logger.info(
                f"  {fastest['data_structure']} with {fastest['num_elements']} elements"
            )
            logger.info(f"  {fastest['ops_per_second']:.0f} ops/sec")

            logger.info(f"\nSlowest configuration:")
            logger.info(
                f"  {slowest['data_structure']} with {slowest['num_elements']} elements"
            )
            logger.info(f"  {slowest['ops_per_second']:.0f} ops/sec")

        logger.info(f"\nResults saved in: {LOCAL_RESULTS_DIR}")
        logger.info("Analysis complete!")
    else:
        logger.error("No results to analyze!")


if __name__ == "__main__":
    main()
