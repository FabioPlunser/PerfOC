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
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Configuration
BASE_WORK_DIR = Path("/scratch/cb761223/exercises/sheet09/datastructure_benchmark")
BENCHMARK_EXECUTABLE = "/scratch/cb761223/exercises/sheet09/src/benchmark"
SLURM_PARTITION = "lva"
SLURM_CPUS_PER_TASK = 4
SLURM_MEMORY = "16G"
SLURM_TIME_LIMIT = "00:01:00"
NUM_REPETITIONS = 3

# Benchmark parameters
DATA_STRUCTURES = ["array", "list_seq", "list_rand"]
INSTRUCTION_MIXES = [
    {"ins_del": 0.0, "read_write": 1.0},
    {"ins_del": 0.01, "read_write": 0.99},
    {"ins_del": 0.10, "read_write": 0.90},
    {"ins_del": 0.50, "read_write": 0.50},
]
ELEMENT_SIZES = [8, 512, 8 * 1024 * 1024]
NUM_ELEMENTS = [10, 1000, 100000, 10000000]

# Directories
SLURM_SCRIPTS_DIR = BASE_WORK_DIR / "slurm_scripts"
SLURM_LOGS_DIR = BASE_WORK_DIR / "slurm_logs"
RESULTS_DIR = BASE_WORK_DIR / "results"
PLOTS_DIR = RESULTS_DIR / "plots"
TABLES_DIR = RESULTS_DIR / "tables"


def setup_directories():
    """Create necessary directories."""
    for directory in [
        BASE_WORK_DIR,
        SLURM_SCRIPTS_DIR,
        SLURM_LOGS_DIR,
        RESULTS_DIR,
        PLOTS_DIR,
        TABLES_DIR,
    ]:
        directory.mkdir(parents=True, exist_ok=True)
    logger.info(f"Working directory: {BASE_WORK_DIR}")


def estimate_memory_usage(num_elements, element_size):
    """Estimate memory usage in MB for a given configuration."""
    # Base memory for the data structure
    base_memory = num_elements * element_size / (1024 * 1024)  # MB

    # Additional overhead for linked lists (pointers, metadata)
    if element_size == 8:  # Assuming int + pointer overhead
        overhead = num_elements * 16 / (1024 * 1024)  # 8 bytes data + 8 bytes pointer
    else:
        overhead = num_elements * (element_size + 16) / (1024 * 1024)

    # Extra space for insertions (benchmark allocates +100 or +extra)
    extra_space = base_memory * 0.1

    total_memory = base_memory + overhead + extra_space
    return total_memory


def should_exclude_combination(ds, num_elements, element_size):
    """Determine if a combination should be excluded due to memory constraints."""
    memory_mb = estimate_memory_usage(num_elements, element_size)

    # Exclude if estimated memory > 12GB (leave some headroom)
    if memory_mb > 12 * 1024:
        logger.info(
            f"Excluding {ds} with {num_elements} elements of {element_size} bytes "
            f"(estimated {memory_mb:.1f} MB)"
        )
        return True

    # Exclude very large linked lists (they'll be extremely slow)
    if ds.startswith("list") and num_elements >= 1000000 and element_size >= 512:
        logger.info(
            f"Excluding slow combination: {ds} with {num_elements} elements of {element_size} bytes"
        )
        return True

    return False


def generate_benchmark_combinations():
    """Generate all valid benchmark parameter combinations."""
    combinations = []
    excluded_count = 0

    for ds, mix, num_elem, elem_size in itertools.product(
        DATA_STRUCTURES, INSTRUCTION_MIXES, NUM_ELEMENTS, ELEMENT_SIZES
    ):
        if should_exclude_combination(ds, num_elem, elem_size):
            excluded_count += 1
            continue

        combinations.append(
            {
                "data_structure": ds,
                "num_elements": num_elem,
                "element_size": elem_size,
                "ins_del_ratio": mix["ins_del"],
                "read_write_ratio": mix["read_write"],
                "estimated_memory_mb": estimate_memory_usage(num_elem, elem_size),
            }
        )

    logger.info(
        f"Generated {len(combinations)} valid combinations, excluded {excluded_count}"
    )
    return combinations


def create_slurm_script(combination, run_id, job_name):
    """Create a SLURM script for a specific benchmark combination."""
    script_path = SLURM_SCRIPTS_DIR / f"{job_name}.sh"
    log_path = SLURM_LOGS_DIR / f"{job_name}.out"

    # Adjust memory based on estimated usage
    estimated_mb = combination["estimated_memory_mb"]
    # if estimated_mb > 8000:
    #     memory = "16G"
    #     time_limit = "02:00:00"
    # elif estimated_mb > 2000:
    #     memory = "8G"
    #     time_limit = "01:00:00"
    # else:
    #     memory = "4G"
    #     time_limit = "00:30:00"

    script_content = f"""#!/bin/bash
#SBATCH --job-name={job_name}
#SBATCH --partition={SLURM_PARTITION}
#SBATCH --cpus-per-task={SLURM_CPUS_PER_TASK}
#SBATCH --time={SLURM_TIME_LIMIT}
#SBATCH --output={log_path}
#SBATCH --error={log_path}

# Load modules if needed
# module load gcc/11.2.0

# Change to benchmark directory
cd {BASE_WORK_DIR.parent}

# Ensure benchmark executable exists
if [ ! -f "{BENCHMARK_EXECUTABLE}" ]; then
    echo "ERROR: Benchmark executable not found at {BENCHMARK_EXECUTABLE}"
    exit 1
fi

# Run benchmark with timing
echo "Starting benchmark: {job_name}"
echo "Data Structure: {combination['data_structure']}"
echo "Elements: {combination['num_elements']}"
echo "Element Size: {combination['element_size']} bytes"
echo "Ins/Del Ratio: {combination['ins_del_ratio']}"
echo "Read/Write Ratio: {combination['read_write_ratio']}"
echo "Estimated Memory: {estimated_mb:.1f} MB"
echo "Timestamp: $(date)"
echo "----------------------------------------"

/usr/bin/time -v {BENCHMARK_EXECUTABLE} \\
    {combination['data_structure']} \\
    {combination['num_elements']} \\
    {combination['read_write_ratio']} \\
    {combination['ins_del_ratio']}

echo "----------------------------------------"
echo "Benchmark completed at: $(date)"
"""

    with open(script_path, "w") as f:
        f.write(script_content)

    # Make script executable
    os.chmod(script_path, 0o755)

    return script_path, log_path


def submit_slurm_job(script_path):
    """Submit a SLURM job and return the job ID."""
    try:
        result = subprocess.run(
            ["sbatch", str(script_path)], capture_output=True, text=True, check=True
        )
        # Extract job ID from output like "Submitted batch job 12345"
        job_id = result.stdout.strip().split()[-1]
        return job_id
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to submit job {script_path}: {e}")
        return None


def wait_for_jobs(job_ids, check_interval=30):
    """Wait for all SLURM jobs to complete."""
    logger.info(f"Waiting for {len(job_ids)} jobs to complete...")

    while job_ids:
        time.sleep(check_interval)

        # Check job status
        try:
            result = subprocess.run(
                ["squeue", "-j", ",".join(job_ids), "-h", "-o", "%i %T"],
                capture_output=True,
                text=True,
                check=True,
            )

            running_jobs = []
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    job_id, status = line.strip().split()
                    if status in ["PENDING", "RUNNING"]:
                        running_jobs.append(job_id)

            completed = len(job_ids) - len(running_jobs)
            logger.info(f"Jobs completed: {completed}/{len(job_ids)}")
            job_ids = running_jobs

        except subprocess.CalledProcessError:
            # If squeue fails, assume jobs are done
            logger.info("Could not check job status, assuming completion")
            break

    logger.info("All jobs completed!")


def parse_benchmark_output(log_path, combination, run_id):
    """Parse benchmark output from SLURM log file."""
    if not log_path.exists():
        logger.warning(f"Log file not found: {log_path}")
        return None

    try:
        with open(log_path, "r") as f:
            content = f.read()

        # Parse benchmark results
        data = {
            "data_structure": combination["data_structure"],
            "num_elements": combination["num_elements"],
            "element_size": combination["element_size"],
            "ins_del_ratio": combination["ins_del_ratio"],
            "read_write_ratio": combination["read_write_ratio"],
            "run_id": run_id,
        }

        # Extract benchmark metrics
        import re

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

        # Parse /usr/bin/time output
        # Maximum resident set size (kbytes): 12345
        rss_match = re.search(r"Maximum resident set size \(kbytes\): (\d+)", content)
        if rss_match:
            data["peak_memory_kb"] = int(rss_match.group(1))
            data["peak_memory_mb"] = data["peak_memory_kb"] / 1024

        # User time (seconds): 0.23
        user_time_match = re.search(r"User time \(seconds\): ([\d\.]+)", content)
        if user_time_match:
            data["user_time_s"] = float(user_time_match.group(1))

        # System time (seconds): 0.01
        sys_time_match = re.search(r"System time \(seconds\): ([\d\.]+)", content)
        if sys_time_match:
            data["system_time_s"] = float(sys_time_match.group(1))

        # Check for errors
        if "ERROR" in content or "Segmentation fault" in content:
            data["error"] = True
            logger.warning(f"Error detected in {log_path}")
        else:
            data["error"] = False

        return data

    except Exception as e:
        logger.error(f"Failed to parse {log_path}: {e}")
        return None


def collect_all_results(combinations):
    """Collect results from all benchmark runs."""
    all_results = []

    for i, combination in enumerate(combinations):
        for run_id in range(1, NUM_REPETITIONS + 1):
            job_name = f"bench_{i:03d}_run{run_id}"
            log_path = SLURM_LOGS_DIR / f"{job_name}.out"

            result = parse_benchmark_output(log_path, combination, run_id)
            if result:
                all_results.append(result)

    return pd.DataFrame(all_results)


def create_summary_tables(df):
    """Create summary tables and save as markdown."""
    if df.empty:
        logger.warning("No data to create tables")
        return

    # Filter successful runs
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
                "peak_memory_mb": ["mean", "std", "min", "max"],
                "cycles_per_op": ["mean", "std", "min", "max"],
            }
        )
        .round(4)
    )

    # Flatten column names
    summary.columns = [f"{col[1]}_{col[0]}" for col in summary.columns]
    summary = summary.reset_index()

    # Save detailed summary
    summary.to_csv(TABLES_DIR / "detailed_summary.csv", index=False)

    # Create markdown table
    with open(TABLES_DIR / "summary.md", "w") as f:
        f.write("# Benchmark Results Summary\n\n")
        f.write("## Performance Overview\n\n")
        f.write(summary.to_markdown(index=False))
        f.write("\n\n")

        # Create performance comparison table
        f.write("## Performance Comparison (Operations per Second)\n\n")
        perf_pivot = success_df.pivot_table(
            values="ops_per_second",
            index=["num_elements", "element_size"],
            columns="data_structure",
            aggfunc="mean",
        ).round(0)
        f.write(perf_pivot.to_markdown())
        f.write("\n\n")

        # Memory usage comparison
        f.write("## Memory Usage Comparison (MB)\n\n")
        mem_pivot = success_df.pivot_table(
            values="peak_memory_mb",
            index=["num_elements", "element_size"],
            columns="data_structure",
            aggfunc="mean",
        ).round(2)
        f.write(mem_pivot.to_markdown())

    logger.info(f"Summary tables saved to {TABLES_DIR}")


def create_plots(df):
    """Create comprehensive plots of benchmark results."""
    if df.empty:
        logger.warning("No data to plot")
        return

    # Filter successful runs
    success_df = df[~df.get("error", True)].copy()

    if success_df.empty:
        logger.warning("No successful runs to plot")
        return

    # Set up plotting style
    plt.style.use("seaborn-v0_8-whitegrid")
    sns.set_palette("husl")

    # 1. Performance vs Data Structure Size
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle("Data Structure Performance Analysis", fontsize=16)

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
        grouped = ds_data.groupby("num_elements")["peak_memory_mb"].mean()
        ax2.loglog(grouped.index, grouped.values, marker="s", label=ds, linewidth=2)
    ax2.set_xlabel("Number of Elements")
    ax2.set_ylabel("Peak Memory (MB)")
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
    plt.savefig(PLOTS_DIR / "performance_overview.png", dpi=300, bbox_inches="tight")
    plt.close()

    # 2. Detailed heatmaps
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
    plt.savefig(PLOTS_DIR / "performance_heatmaps.png", dpi=300, bbox_inches="tight")
    plt.close()

    # 3. Box plots for variability analysis
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))

    # Performance variability
    sns.boxplot(data=success_df, x="data_structure", y="ops_per_second", ax=axes[0, 0])
    axes[0, 0].set_yscale("log")
    axes[0, 0].set_title("Performance Variability by Data Structure")
    axes[0, 0].tick_params(axis="x", rotation=45)

    # Memory variability
    sns.boxplot(data=success_df, x="data_structure", y="peak_memory_mb", ax=axes[0, 1])
    axes[0, 1].set_yscale("log")
    axes[0, 1].set_title("Memory Usage Variability by Data Structure")
    axes[0, 1].tick_params(axis="x", rotation=45)

    # Performance by instruction mix
    sns.boxplot(
        data=success_df,
        x="ins_del_ratio",
        y="ops_per_second",
        hue="data_structure",
        ax=axes[1, 0],
    )
    axes[1, 0].set_yscale("log")
    axes[1, 0].set_title("Performance by Instruction Mix")

    # Cycles per operation
    if "cycles_per_op" in success_df.columns:
        sns.boxplot(
            data=success_df, x="data_structure", y="cycles_per_op", ax=axes[1, 1]
        )
        axes[1, 1].set_yscale("log")
        axes[1, 1].set_title("CPU Cycles per Operation")
        axes[1, 1].tick_params(axis="x", rotation=45)

    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "variability_analysis.png", dpi=300, bbox_inches="tight")
    plt.close()

    logger.info(f"Plots saved to {PLOTS_DIR}")


d


def main():
    """Main function to orchestrate the entire benchmark suite."""
    start_time = time.time()

    logger.info("Starting comprehensive data structure benchmark suite")
    setup_directories()

    # Generate all benchmark combinations
    combinations = generate_benchmark_combinations()

    # Save combinations for reference
    with open(RESULTS_DIR / "combinations.json", "w") as f:
        json.dump(combinations, f, indent=2)

    logger.info(f"Total combinations to test: {len(combinations)}")
    logger.info(f"Total jobs to submit: {len(combinations) * NUM_REPETITIONS}")

    # Create and submit SLURM jobs
    job_ids = []

    for i, combination in enumerate(combinations):
        for run_id in range(1, NUM_REPETITIONS + 1):
            job_name = f"bench_{i:03d}_run{run_id}"
            script_path, log_path = create_slurm_script(combination, run_id, job_name)

            job_id = submit_slurm_job(script_path)
            if job_id:
                job_ids.append(job_id)
                logger.info(f"Submitted job {job_id}: {job_name}")
            else:
                logger.error(f"Failed to submit job: {job_name}")

    logger.info(f"Submitted {len(job_ids)} jobs to SLURM")

    # Wait for all jobs to complete
    if job_ids:
        wait_for_jobs(job_ids)

    # Collect and analyze results
    logger.info("Collecting results...")
    results_df = collect_all_results(combinations)

    if not results_df.empty:
        # Save raw results
        results_df.to_csv(RESULTS_DIR / "raw_results.csv", index=False)

        # Create summary tables
        create_summary_tables(results_df)

        # Create plots
        create_plots(results_df)

        # Print summary statistics
        logger.info("\n" + "=" * 50)
        logger.info("BENCHMARK SUMMARY")
        logger.info("=" * 50)
        logger.info(f"Total combinations tested: {len(combinations)}")
        logger.info(f"Total runs: {len(results_df)}")
        logger.info(
            f"Successful runs: {len(results_df[~results_df.get('error', True)])}"
        )
        logger.info(f"Failed runs: {len(results_df[results_df.get('error', True)])}")

        # Performance highlights
        success_df = results_df[~results_df.get("error", True)]
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

    else:
        logger.error("No results collected!")

    end_time = time.time()
    total_time = datetime.timedelta(seconds=end_time - start_time)
    logger.info(f"\nTotal execution time: {total_time}")
    logger.info(f"Results saved in: {RESULTS_DIR}")


if __name__ == "__main__":
    main()
