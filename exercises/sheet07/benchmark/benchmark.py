#!/usr/bin/env python3

import os
import sys
import subprocess
import re
import time
import datetime
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import logging
import shutil

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("benchmark.log")],
)

BASE_WORK_DIR = Path("/scratch/cb761223/exercises/sheet07/benchmark")
ALLSCALE_API_REPO = "https://github.com/allscale/allscale_api.git"
RPMALLOC_REPO = "https://github.com/mjansson/rpmalloc.git"
MIMALLOC_REPO = "https://github.com/microsoft/mimalloc.git"

LLVM_MODULE = "llvm/15.0.4-python-3.10.8-gcc-8.5.0-bq44zh7"
SLURM_PARTITION = "lva"
SLURM_CPUS_PER_TASK = 16
SLURM_MEMORY = "32G"
SLURM_TIME_LIMIT = "02:00:00"

NUM_REPETITIONS = 3
ALLOCATORS = {
    "none": None,
    "rpmalloc": "librpmalloc.so",
    "mimalloc": "libmimalloc.so",
}

ALLSCALE_SRC_DIR = BASE_WORK_DIR / "allscale_api"
ALLOCATORS_BASE_DIR = BASE_WORK_DIR / "allocators"
SLURM_SCRIPTS_DIR = BASE_WORK_DIR / "slurm_scripts"  # Not used anymore
SLURM_LOGS_DIR = BASE_WORK_DIR / "slurm_logs"
JOB_METRICS_DIR = BASE_WORK_DIR / "job_metrics_output"
RESULTS_DIR = BASE_WORK_DIR / "results"
CSV_RESULTS_FILE = RESULTS_DIR / "benchmark_summary.csv"

def run_command(command, cwd=None, env=None, check=True, capture_output=True):
    """Executes a shell command."""
    print(f"Running command: {' '.join(command)} {'in ' + str(cwd) if cwd else ''}")
    process = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        capture_output=capture_output,
        text=True,
    )
    if check and process.returncode != 0:
        print(f"Error running command: {' '.join(command)}")
        print(f"Stdout:\n{process.stdout}")
        print(f"Stderr:\n{process.stderr}")
        raise RuntimeError(f"Command failed: {' '.join(command)}")
    return process

def setup_directories():
    """Creates necessary directories in /scratch and /tmp."""
    print("Setting up directories...")
    BASE_WORK_DIR.mkdir(parents=True, exist_ok=True)  # /scratch
    ALLSCALE_SRC_DIR.parent.mkdir(parents=True, exist_ok=True)
    ALLOCATORS_BASE_DIR.mkdir(parents=True, exist_ok=True)
    SLURM_SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)  # Keeping for now
    SLURM_LOGS_DIR.mkdir(parents=True, exist_ok=True)  # /scratch
    JOB_METRICS_DIR.mkdir(parents=True, exist_ok=True)  # /scratch
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)  # /scratch
    print(f"Base working directory: {BASE_WORK_DIR}")

def clean_cmake_cache(src_dir):
    """Removes CMake-related files from the source directory."""
    cmake_files = [
        src_dir / "CMakeCache.txt",
        src_dir / "CMakeFiles",
        src_dir / "CMakeLists.txt.user",
    ]
    for item in cmake_files:
        if item.exists():
            if item.is_dir():
                shutil.rmtree(item)
                logger.info(f"Removed directory: {item}")
            else:
                item.unlink()
                logger.info(f"Removed file: {item}")

def build_allscale(allocator_key, run_idx, allocator_so_path=None):
    """Builds the allscale_api project in /tmp with the specified allocator."""

    allocator_name_fs = allocator_key.replace(" ", "_")
    tmp_base_dir = Path(f"/tmp/cb761223")
    tmp_dir = tmp_base_dir / f"allocbench_{allocator_name_fs}_run{run_idx}"
    tmp_src_dir = tmp_dir / "allscale_api_code"
    tmp_code_dir = tmp_src_dir / "code"  # Add this line
    build_dir = tmp_dir / "build"
    metrics_file = JOB_METRICS_DIR / f"metrics_{allocator_key}_run{run_idx}.txt"

    # Ensure /tmp base dir exists (handle potential race conditions)
    tmp_base_dir.mkdir(parents=True, exist_ok=True)

    # Cleanup and recreate the /tmp directory for this run
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=False)  # Create fresh

    # **Clean the source directory BEFORE copying**
    clean_cmake_cache(ALLSCALE_SRC_DIR)

    # Copy the source code to the /tmp directory
    shutil.copytree(ALLSCALE_SRC_DIR, tmp_src_dir)
    build_dir.mkdir(parents=True, exist_ok=True)

    logger.info(
        f"Building Allscale with {allocator_key} in {build_dir}, run {run_idx}"
    )

    # Module loading (important to do *inside* the build function)
    module_load_cmds = f"module load {LLVM_MODULE}" if LLVM_MODULE else ""
    if module_load_cmds:
        run_command(["/bin/bash", "-c", module_load_cmds], cwd=build_dir)

    cmake_cmd = [
        "cmake",
        "-DCMAKE_BUILD_TYPE=Release",
        "-G",
        "Ninja",
        str(tmp_code_dir),  # Use tmp_code_dir instead of tmp_src_dir
    ]
    run_command(cmake_cmd, cwd=build_dir)

    ninja_clean_cmd = ["ninja", "clean"]
    run_command(ninja_clean_cmd, cwd=build_dir)

    env = os.environ.copy()  # Important: Copy the environment
    if allocator_so_path:
        env["LD_PRELOAD"] = str(allocator_so_path.resolve())
    else:
        env.pop("LD_PRELOAD", None)  # Remove LD_PRELOAD if no allocator

    ninja_build_cmd = ["/usr/bin/time", "-v", "ninja", "-j", str(SLURM_CPUS_PER_TASK)]
    try:
        result = run_command(
            ninja_build_cmd,
            cwd=build_dir,
            env=env,
            capture_output=True,  
            check=True,
        )  
        logger.info(f"Ninja build succeeded: {result}")
        with open(metrics_file, "w") as metrics_output:
            metrics_output.write(result.stdout)
            metrics_output.write(result.stderr)
        print(f"Metrics written to {metrics_file}")
        build_succeeded = True
        exit_code = 0  # Indicate success
    except subprocess.CalledProcessError as e:
        print(f"Ninja build failed: {e}")
        build_succeeded = False
        exit_code = e.returncode  # Capture the return code from ninja

    # Parse time output if build succeeded (or even if not, try to get something)
    parsed_data = parse_time_output(metrics_file)

    # Cleanup /tmp directory after the build is complete (success or failure)
    shutil.rmtree(tmp_dir)

    return build_succeeded, metrics_file, parsed_data, exit_code


def parse_time_output(file_path):
    """Parses /usr/bin/time -v output."""
    if not file_path.exists() or file_path.stat().st_size == 0:
        print(f"Warning: Metrics file {file_path} is missing or empty.")
        return None

    with open(file_path, "r") as f:
        content = f.read()

    data = {}
    # User time (seconds): 0.23
    user_time_match = re.search(r"User time \(seconds\):\s*([\d\.]+)", content)
    if user_time_match:
        data["UserTime_s"] = float(user_time_match.group(1))

    # System time (seconds): 0.01
    system_time_match = re.search(r"System time \(seconds\):\s*([\d\.]+)", content)
    if system_time_match:
        data["SystemTime_s"] = float(system_time_match.group(1))

    # Elapsed (wall clock) time (h:mm:ss or m:ss): 0:00.25 or 0.25
    wall_time_match = re.search(
        r"Elapsed \(wall clock\) time \(h:mm:ss or m:ss\):\s*([^\n]+)", content
    )
    if wall_time_match:
        time_str = wall_time_match.group(1).strip()
        parts = list(map(float, time_str.split(":")))
        if len(parts) == 3:  # h:mm:ss
            data["WallTime_s"] = parts[0] * 3600 + parts[1] * 60 + parts[2]
        elif len(parts) == 2:  # m:ss
            data["WallTime_s"] = parts[0] * 60 + parts[1]
        elif len(parts) == 1:  # s.ss
            data["WallTime_s"] = parts[0]
        else:
            print(
                f"Warning: Could not parse wall time '{time_str}' from {file_path}"
            )

    # Maximum resident set size (kbytes): 12345
    rss_match = re.search(
        r"Maximum resident set size \(kbytes\):\s*(\d+)", content
    )
    if rss_match:
        data["PeakRSS_KB"] = int(rss_match.group(1))

    # Exit status: 0
    exit_status_match = re.search(r"Exit status:\s*(\d+)", content)
    if exit_status_match:  # This is from /usr/bin/time itself
        data["TimeCommandExitCode"] = int(exit_status_match.group(1))

    # Check if ninja build itself failed (based on our slurm script structure)
    if (
        "ERROR: Ninja build failed" in content or "Exit status:" not in content
    ):
        data["BuildSucceeded"] = False
    elif "TimeCommandExitCode" in data and data["TimeCommandExitCode"] == 0:
        data["BuildSucceeded"] = True
    else:
        data["BuildSucceeded"] = False

    if not all(
        k in data for k in ["UserTime_s", "SystemTime_s", "WallTime_s", "PeakRSS_KB"]
    ):
        print(
            f"Warning: Could not parse all required metrics from {file_path}. Content:\n{content[:500]}..."
        )
        return None

    return data

def collect_all_results(job_details_list):
    """Collects results from all job metric files."""
    all_data = []
    for details in job_details_list:
        alloc_key = details["allocator_key"]
        run_idx = details["run_idx"]
        metrics_file = details["metrics_file"]
        exit_code = details["exit_code"]
        parsed_data = details["parsed_data"]

        if parsed_data:
            entry = {
                "Allocator": alloc_key,
                "Run": run_idx,
                **parsed_data,
            }
            if not parsed_data.get("BuildSucceeded", False):
                print(
                    f"Warning: Build for {alloc_key} run {run_idx} reported as failed or metrics incomplete."
                )
                entry["ExitCode"] = exit_code
            else:
                entry["ExitCode"] = 0
            all_data.append(entry)
        else:
            all_data.append(
                {
                    "Allocator": alloc_key,
                    "Run": run_idx,
                    "ExitCode": exit_code,
                }
            )
            print(
                f"Failed to parse results for {alloc_key} run {run_idx} from {metrics_file}"
            )

    return pd.DataFrame(all_data)

def generate_plots(df):
    """Generates and saves plots from the benchmark data."""
    if df.empty:
        print("No data to plot.")
        return

    successful_df = df[df["ExitCode"] == 0].copy()
    if successful_df.empty:
        print("No successful runs to plot.")
        return

    successful_df.loc[:, "CPUTime_s"] = (
        successful_df["UserTime_s"] + successful_df["SystemTime_s"]
    )
    successful_df.loc[:, "PeakRSS_MB"] = successful_df["PeakRSS_KB"] / 1024

    allocator_order = sorted(
        successful_df["Allocator"].unique(), key=lambda x: (x != "none", x)
    )

    plt.style.use("seaborn-v0_8-whitegrid")

    plt.figure(figsize=(10, 6))
    sns.barplot(
        x="Allocator",
        y="CPUTime_s",
        data=successful_df,
        order=allocator_order,
        capsize=0.1,
        errorbar="sd",
    )
    plt.title("Mean CPU Time (Lower is Better)")
    plt.ylabel("CPU Time (seconds)")
    plt.savefig(RESULTS_DIR / "benchmark_cpu_time.png")
    plt.close()
    print(f"Saved CPU time plot to {RESULTS_DIR / 'benchmark_cpu_time.png'}")

    plt.figure(figsize=(10, 6))
    sns.barplot(
        x="Allocator",
        y="WallTime_s",
        data=successful_df,
        order=allocator_order,
        capsize=0.1,
        errorbar="sd",
    )
    plt.title("Mean Wall Time (Lower is Better)")
    plt.ylabel("Wall Time (seconds)")
    plt.savefig(RESULTS_DIR / "benchmark_wall_time.png")
    print(f"Saved Wall time plot to {RESULTS_DIR / 'benchmark_wall_time.png'}")

    plt.figure(figsize=(10, 6))
    sns.barplot(
        x="Allocator",
        y="PeakRSS_MB",
        data=successful_df,
        order=allocator_order,
        capsize=0.1,
        errorbar="sd",
    )
    plt.title("Mean Peak Memory Consumption (Lower is Better)")
    plt.ylabel("Peak RSS (MB)")
    plt.savefig(RESULTS_DIR / "benchmark_peak_memory.png")
    plt.close()
    print(f"Saved Peak memory plot to {RESULTS_DIR / 'benchmark_peak_memory.png'}")

# --- Main Orchestration ---
def main():
    """Main function to orchestrate the benchmark."""
    start_time_total = time.time()
    setup_directories()

    allocator_paths = {}
    allocator_paths["rpmalloc"] = Path(
        "/scratch/cb761223/exercises/sheet07/benchmark/allocators/librpmalloc.so"
    )
    allocator_paths["mimalloc"] = Path(
        "/scratch/cb761223/exercises/sheet07/benchmark/allocators/libmimalloc.so"
    )
    allocator_paths["none"] = None

    job_details_for_results = []

    for allocator_key, lib_name in ALLOCATORS.items():
        alloc_so_path = allocator_paths[allocator_key] if lib_name else None
        for i in range(1, NUM_REPETITIONS + 1):
            logger.info(
                f"\nBuilding and running for Allocator: {allocator_key}, Run: {i}"
            )
            build_succeeded, metrics_file, parsed_data, exit_code = build_allscale(
                allocator_key, i, alloc_so_path
            )

            job_details_for_results.append(
                {
                    "allocator_key": allocator_key,
                    "run_idx": i,
                    "metrics_file": metrics_file,
                    "exit_code": exit_code,
                    "parsed_data": parsed_data,
                }
            )

    print("\nCollecting and processing results...")
    results_df = collect_all_results(job_details_for_results)

    if results_df.empty:
        print("No results collected. Check logs and metric files.")
    else:
        print("\n--- Benchmark Data ---")
        print(results_df.to_string())
        results_df.to_csv(CSV_RESULTS_FILE, index=False)
        print(f"\nResults saved to {CSV_RESULTS_FILE}")

        print("\nGenerating plots...")
        generate_plots(results_df)

    end_time_total = time.time()
    logger.info(
        f"Total benchmark suite execution time: {datetime.timedelta(seconds=end_time_total - start_time_total)}"
    )
    logger.info(f"All outputs are in: {BASE_WORK_DIR}")

if __name__ == "__main__":
    main()
