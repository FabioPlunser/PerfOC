#!/usr/bin/env python3
import os
import sys
import subprocess
import shlex
import time
import re
import stat
from pathlib import Path
import shutil
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# --- Configuration ---

# Benchmark Setup
MATRIX_SIZE = 2048
# Tile sizes for the tiled version (0 means tiled code runs non-tiled logic)
TILE_SIZES_TO_TEST = [0,2, 4,8, 16, 32, 64, 128]
NUM_RUNS = 5  # Number of times to run each variant (baseline and each tile size)
C_SOURCE_BASELINE = "mmul.c"      # Baseline implementation
C_SOURCE_TILED = "mmul_tiled.c" # Tiled implementation

# Directory Setup
BASE_OUTPUT_DIR = Path("./mmul_comparison_benchmark") # Base for all output
BUILD_DIR = BASE_OUTPUT_DIR / "build"
SLURM_SCRIPTS_DIR = BASE_OUTPUT_DIR / "slurm_scripts"
SLURM_LOGS_DIR = BASE_OUTPUT_DIR / "slurm_logs"
RESULTS_DIR = BASE_OUTPUT_DIR / "results"

# Slurm Configuration (ADJUST FOR LCC3)
SLURM_PARTITION = "lva"  # Partition name
SLURM_TIME = "00:45:00"  # Max job time (HH:MM:SS)
# Add account if needed: SLURM_ACCOUNT = "YourAccount"
SLURM_ACCOUNT = ""
SLURM_JOB_POLL_INTERVAL = 30  # Seconds between checking job status
SLURM_SUBMIT_DELAY = 0.1  # Seconds delay between submitting jobs

# Build Configuration
COMPILER = "gcc"
OPTIMIZATION_FLAGS = ["-O3"]
EXTRA_COMPILE_FLAGS = ["-Wall", "-Wextra", "-lm"]  # Link math library
COMPILE_DEFINES = [f"-DS={MATRIX_SIZE}"]  # Pass matrix size define
EXECUTABLE_BASELINE_NAME = "mmul_baseline_exec"
EXECUTABLE_TILED_NAME = "mmul_tiled_exec"

# --- Helper Functions ---

def run_command(command, cwd=None, check=False, capture=False, verbose=True):
    """Runs a shell command."""
    if isinstance(command, str):
        command = shlex.split(command)
    if verbose:
        print(f"Running: {' '.join(command)}")
    kwargs = {"cwd": cwd, "text": True}
    if capture:
        kwargs["capture_output"] = True
    try:
        result = subprocess.run(command, check=check, **kwargs)
        return result
    except Exception as e:
        print(f"--- Error running command ---")
        print(f"Command: {' '.join(command)}")
        print(f"Error: {e}")
        if isinstance(e, subprocess.CalledProcessError):
             if capture:
                 print(f"Stderr:\n{e.stderr}")
                 print(f"Stdout:\n{e.stdout}")
             print(f"Return Code: {e.returncode}")
        print(f"-----------------------------")
        if check: raise
        return subprocess.CompletedProcess(command, -1, stdout="", stderr=str(e))


def compile_c_code(source_path, exe_path):
    """Compiles a C source file."""
    source_path = Path(source_path)
    exe_path = Path(exe_path)
    if not source_path.is_file():
        print(f"ERROR: C source file '{source_path}' not found.")
        return None

    compile_command = (
        [
            COMPILER,
            str(source_path),
            "-o",
            str(exe_path),
        ]
        + OPTIMIZATION_FLAGS
        + COMPILE_DEFINES
        + EXTRA_COMPILE_FLAGS
    )

    print(f"\n--- Compiling {source_path.name} ---")
    result = run_command(compile_command, capture=True)

    if result.returncode != 0:
        print(f"ERROR: Compilation failed for {source_path.name}.")
        return None
    else:
        print(f"Successfully compiled {source_path.name} to {exe_path}")
        if result.stderr:
            print(f"Compiler Warnings/Messages:\n{result.stderr}")
        return exe_path

def generate_and_submit_slurm(prog_type, tile_size, run_idx, exe_path):
    """Generates a Slurm script and submits it.
       prog_type: 'baseline' or 'tiled'
       tile_size: Integer tile size (or None/-1 for baseline)
    """
    if prog_type == 'baseline':
        job_name = f"mmul_baseline_run{run_idx + 1}"
        tile_size_arg = "" # Baseline takes no argument
        tile_size_info = "N/A"
    elif prog_type == 'tiled':
        job_name = f"mmul_tiled_tile{tile_size}_run{run_idx + 1}"
        tile_size_arg = f"{tile_size}" # Tiled takes tile size argument
        tile_size_info = str(tile_size)
    else:
        print(f"ERROR: Unknown program type '{prog_type}'")
        return None

    script_path = SLURM_SCRIPTS_DIR / f"{job_name}.sh"
    log_path = SLURM_LOGS_DIR / f"{job_name}.log"

    run_command_str = f"{exe_path.resolve()} {tile_size_arg}".strip() # Add arg only if needed
    timed_command = f"time -p {run_command_str}"  # Use time -p

    account_line = f"#SBATCH --account={SLURM_ACCOUNT}" if SLURM_ACCOUNT else ""

    script_content = f"""#!/bin/bash
#SBATCH --partition={SLURM_PARTITION}
#SBATCH --job-name={job_name}
#SBATCH --output={log_path.resolve()}
#SBATCH --error={log_path.resolve()} # Combine stdout/stderr
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --time={SLURM_TIME}
#SBATCH --exclusive
{account_line}

echo "--- Job Info ---"
echo "Job ID: $SLURM_JOB_ID"
echo "Job Name: $SLURM_JOB_NAME"
echo "Program Type: {prog_type}"
echo "Tile Size: {tile_size_info}"
echo "Run Index: {run_idx + 1}/{NUM_RUNS}"
echo "Executable: {exe_path.resolve()}"
echo "Log File: {log_path.resolve()}"
echo "Job started on $(hostname) at $(date)"

echo "--- Execution ---"
echo "Running command: {timed_command}"
echo "-------------------- Program Output Start --------------------"

{timed_command}

exit_code=$?
echo "-------------------- Program Output End ----------------------"
echo "--- Completion ---"
echo "Command finished with exit code: $exit_code"
echo "Job finished at: $(date)"

exit $exit_code
"""
    # Write script
    try:
        script_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(script_path, "w") as f:
            f.write(script_content)
        script_path.chmod(script_path.stat().st_mode | stat.S_IEXEC)
    except Exception as e:
        print(f"ERROR: Failed to write Slurm script {script_path}: {e}")
        return None

    # Submit script
    sbatch_cmd = ["sbatch", str(script_path)]
    try:
        result = run_command(sbatch_cmd, check=True, capture=True, verbose=False)
        job_id_match = re.search(r"Submitted batch job (\d+)", result.stdout)
        if job_id_match:
            job_id = job_id_match.group(1)
            print(f"  Submitted {job_name}: {job_id}")
            return job_id
        else:
            print(f"WARNING: Submitted {job_name} but could not parse Job ID.")
            return "UNKNOWN"
    except Exception as e:
        print(f"ERROR: Failed to submit job {job_name}: {e}")
        return None


def wait_for_slurm_jobs(job_ids):
    """Waits for all jobs in the list to complete."""
    if not job_ids: return
    print(f"\n--- Waiting for {len(job_ids)} Slurm jobs ---")
    active_job_ids = set(job_ids)
    while active_job_ids:
        user = os.environ.get("USER")
        if not user:
            print("ERROR: Cannot determine username ($USER). Stopping wait.")
            break
        squeue_cmd = ["squeue", "-u", user, "-h", "-o", "%i", "-t", "PD,R"]
        result = run_command(squeue_cmd, capture=True, verbose=False, check=False)
        current_active = set(result.stdout.split()) if result.returncode == 0 else set()
        active_job_ids = active_job_ids.intersection(current_active)
        if active_job_ids:
            print(f"{len(active_job_ids)} jobs still pending/running. Waiting {SLURM_JOB_POLL_INTERVAL}s...")
            time.sleep(SLURM_JOB_POLL_INTERVAL)
        else:
            print("All submitted jobs seem to have completed.")
            break


# Regex to capture 'real' time from `time -p` output
TIME_P_REGEX = re.compile(r"^real\s+(\d+\.?\d*)", re.MULTILINE)

def parse_log(log_path: Path):
    """Parses a single Slurm log file for real time and verification status."""
    real_time = None
    verified = None
    exit_code = None
    if not log_path.is_file(): return real_time, verified, exit_code

    try:
        with open(log_path, 'r') as f:
            content = f.read()
        time_match = TIME_P_REGEX.search(content)
        if time_match:
            real_time = float(time_match.group(1))

        if "Verification: OK" in content: verified = True
        elif "Verification: ERR" in content: verified = False

        exit_match = re.search(r"Command finished with exit code: (\d+)", content)
        if exit_match: exit_code = int(exit_match.group(1))

    except Exception as e:
        print(f"Warning: Error parsing log file {log_path.name}: {e}")
    return real_time, verified, exit_code


def analyze_and_plot():
    """Parses all logs, aggregates results, prints table, and plots."""
    print("\n--- Analyzing Results ---")
    all_results = []

    # Parse baseline logs
    for i in range(NUM_RUNS):
        job_name = f"mmul_baseline_run{i + 1}"
        log_file = SLURM_LOGS_DIR / f"{job_name}.log"
        real_time, verified, exit_code = parse_log(log_file)
        all_results.append({
            "ProgType": "baseline",
            "TileSize": -1, # Use -1 or NaN to denote baseline
            "RunIndex": i + 1,
            "RealTime": real_time,
            "Verified": verified,
            "ExitCode": exit_code,
        })

    # Parse tiled logs
    for tile_size in TILE_SIZES_TO_TEST:
        for i in range(NUM_RUNS):
            job_name = f"mmul_tiled_tile{tile_size}_run{i + 1}"
            log_file = SLURM_LOGS_DIR / f"{job_name}.log"
            real_time, verified, exit_code = parse_log(log_file)
            all_results.append({
                "ProgType": "tiled",
                "TileSize": tile_size,
                "RunIndex": i + 1,
                "RealTime": real_time,
                "Verified": verified,
                "ExitCode": exit_code,
            })

    df = pd.DataFrame(all_results)
    # Create label for plotting/grouping
    df['VariantLabel'] = df.apply(
        lambda row: 'Baseline' if row['ProgType'] == 'baseline'
                    else f"Tiled ({row['TileSize']})" if row['TileSize'] > 0
                    else "Tiled (Original Loop)", # Tiled with tile_size=0
        axis=1
    )
    df['TileSizePlot'] = df['TileSize'].replace(-1, np.nan) # Use NaN for baseline x-value

    print("\n--- Raw Parsed Results ---")
    print(df[['ProgType', 'TileSize', 'RunIndex', 'RealTime', 'Verified', 'ExitCode']].to_string(index=False))
    print("--------------------------")

    # Filter for valid runs before aggregation
    valid_runs = df.dropna(subset=['RealTime'])
    valid_runs = valid_runs[valid_runs['ExitCode'] == 0]
    # Optional: Filter only verified runs
    # valid_runs = valid_runs[valid_runs['Verified'] == True]

    if valid_runs.empty:
        print("\nERROR: No successful runs with valid time found for aggregation/plotting.")
        return

    # Aggregate results (Group by Program Type and Tile Size)
    agg_df = (
        valid_runs.groupby(['ProgType', 'TileSize'])['RealTime']
        .agg(['mean', 'std', 'count'])
        .reset_index()
    )
    # Add back labels
    label_map = valid_runs[['ProgType', 'TileSize', 'VariantLabel']].drop_duplicates()
    agg_df = pd.merge(agg_df, label_map, on=['ProgType', 'TileSize'], how='left')
    agg_df['std'] = agg_df['std'].fillna(0) # Handle cases with only 1 valid run

    print("\n--- Aggregated Results (Successful Runs) ---")
    # Sort the DataFrame first
    agg_df_sorted = agg_df.sort_values(by=['ProgType', 'TileSize'])

    # Now select columns, rename, and print
    print(
        agg_df_sorted[['VariantLabel', 'mean', 'std', 'count']] # Select from sorted DF
        .rename(columns={'mean': 'MeanTime', 'std': 'StdDev', 'count': 'ValidRuns'})
        .to_string(index=False, float_format="%.3f")
    )
    print("--------------------------------------------")

    # --- Plotting ---
    plt.figure(figsize=(12, 7))

    # Separate data for plotting
    baseline_agg = agg_df[agg_df['ProgType'] == 'baseline']
    tiled_agg = agg_df[agg_df['ProgType'] == 'tiled'].sort_values(by='TileSize')

    # Plot Baseline line
    if not baseline_agg.empty:
        bl_mean = baseline_agg['mean'].iloc[0]
        bl_std = baseline_agg['std'].iloc[0]
        plt.axhline(bl_mean, color='red', linestyle='--', linewidth=2,
                    label=f'Baseline ({bl_mean:.2f}s)')
        # Add error band for baseline
        plt.axhspan(bl_mean - bl_std, bl_mean + bl_std, color='red', alpha=0.1,
                    label=f'_nolegend_ (StdDev: {bl_std:.2f}s)')

    # Plot Tiled data points with error bars
    if not tiled_agg.empty:
        # Separate tile_size=0 from others for clarity if needed, or plot all
        tiled_plot_data = tiled_agg # Plot all tiled results including tile_size=0
        plt.errorbar(
            tiled_plot_data['TileSize'],
            tiled_plot_data['mean'],
            yerr=tiled_plot_data['std'],
            marker='o',
            linestyle='-',
            capsize=5,
            label='Tiled (Mean +/- StdDev)',
            color='blue' # Explicit color
        )
        # Set x-axis for tiled results
        plt.xscale('log', base=2)
        # Filter ticks to only show actual tested tile sizes > 0
        tiled_ticks = tiled_plot_data[tiled_plot_data['TileSize'] > 0]['TileSize'].unique()
        plt.xticks(sorted(tiled_ticks), sorted(tiled_ticks)) # Set ticks for log scale

    plt.xlabel("Tile Size (Log Scale for Tiled Variants)")
    plt.ylabel("Execution Time (seconds)")
    plt.title(
        f"Matrix Multiplication ({MATRIX_SIZE}x{MATRIX_SIZE}) Performance Comparison\n({NUM_RUNS} runs per variant)"
    )
    plt.legend()
    plt.grid(True, which="both", ls="--") # Grid on both axes

    # Annotate best tiled point (excluding tile_size=0)
    best_tiled_data = tiled_agg[tiled_agg['TileSize'] > 0]
    if not best_tiled_data.empty:
        best_tiled = best_tiled_data.loc[best_tiled_data['mean'].idxmin()]
        plt.annotate(
            f'Best Tiled: {best_tiled["mean"]:.2f}s\n@ Tile Size {int(best_tiled["TileSize"])}',
            xy=(best_tiled['TileSize'], best_tiled['mean']),
            xytext=(
                best_tiled['TileSize'],
                best_tiled['mean'] + (plt.ylim()[1] - plt.ylim()[0]) * 0.1,
            ),
            arrowprops=dict(facecolor='black', shrink=0.05, width=1, headwidth=8),
            ha='center',
        )

    plt.tight_layout()
    plot_path = RESULTS_DIR / "mmul_comparison_plot.png"
    plot_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(plot_path)
    print(f"\nPlot saved to: {plot_path}")


# --- Main Execution ---

def main():
    # --- Setup ---
    if not Path(C_SOURCE_BASELINE).is_file():
        print(f"ERROR: Baseline C source file '{C_SOURCE_BASELINE}' not found.")
        sys.exit(1)
    if not Path(C_SOURCE_TILED).is_file():
        print(f"ERROR: Tiled C source file '{C_SOURCE_TILED}' not found.")
        sys.exit(1)

    # Clean previous run? (Optional)
    # if BASE_OUTPUT_DIR.exists(): shutil.rmtree(BASE_OUTPUT_DIR)

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    SLURM_SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    SLURM_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # --- Compile ---
    exe_baseline_path = BUILD_DIR / EXECUTABLE_BASELINE_NAME
    exe_tiled_path = BUILD_DIR / EXECUTABLE_TILED_NAME

    compiled_baseline = compile_c_code(C_SOURCE_BASELINE, exe_baseline_path)
    compiled_tiled = compile_c_code(C_SOURCE_TILED, exe_tiled_path)

    if not compiled_baseline or not compiled_tiled:
        print("ERROR: Compilation failed for one or both programs. Exiting.")
        sys.exit(1)

    # --- Generate & Submit Jobs ---
    print("\n--- Submitting Slurm Jobs ---")
    submitted_job_ids = []

    # Submit baseline jobs
    print("Submitting Baseline runs...")
    for i in range(NUM_RUNS):
        job_id = generate_and_submit_slurm('baseline', -1, i, compiled_baseline)
        if job_id and job_id != "UNKNOWN":
            submitted_job_ids.append(job_id)
        time.sleep(SLURM_SUBMIT_DELAY)

    # Submit tiled jobs
    print("Submitting Tiled runs...")
    for tile_size in TILE_SIZES_TO_TEST:
        for i in range(NUM_RUNS):
            job_id = generate_and_submit_slurm('tiled', tile_size, i, compiled_tiled)
            if job_id and job_id != "UNKNOWN":
                submitted_job_ids.append(job_id)
            time.sleep(SLURM_SUBMIT_DELAY)

    if not submitted_job_ids:
        print("\nERROR: No jobs were submitted successfully. Exiting.")
        sys.exit(1)
    print(f"\nSuccessfully submitted {len(submitted_job_ids)} jobs in total.")

    # --- Wait for Jobs ---
    wait_for_slurm_jobs(submitted_job_ids)

    # --- Analyze & Plot ---
    analyze_and_plot()

    print("\nBenchmark finished.")

if __name__ == "__main__":
    main()
