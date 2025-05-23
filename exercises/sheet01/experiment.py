#!/usr/bin/env python3

import os
import subprocess
import csv
import statistics
from pathlib import Path
import json
import time
import matplotlib.pyplot as plt  # Import matplotlib
import pandas as pd  # Import pandas for easier data handling

# Set up directories
SCRIPT_DIR = Path("/scratch/cb761223/perf-oriented-dev/small_samples/")
CURRENT_DIR = Path("/scratch/cb761223/perf-oriented-dev/exercises/sheet_01/")

BUILD_DIR = SCRIPT_DIR / "build"
RESULTS_DIR = CURRENT_DIR / "experiment_results"

# Create directories if they don't exist
BUILD_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)

# Build the programs
def build_programs():
    print("Building programs...")
    os.chdir(BUILD_DIR)

    # Run CMake if not already configured
    if not (BUILD_DIR / "build.ninja").exists():
        subprocess.run(
            ["cmake", "..", "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release"],
            check=True,
        )

    # Build all programs
    subprocess.run(["ninja"], check=True)

    os.chdir(SCRIPT_DIR)
    print("Build complete.")


# Global variable for repetitions
REPETITIONS = 3

# Define benchmark configurations - simplified with fewer variations
BENCHMARKS = {
    "delannoy": {
        "params": ["10", "14"],  # Just two N values
    },
    "file_generator": {
        "params": [
            "5 100 1024 10240 1234",
            "10 200 1024 102400 1234",
        ],
        "param_labels": ["small", "medium"],
    },
    "find_largest_file": {
        "params": [""],  # No parameters
    },
    "matrix_mult": {
        "params": [""],  # No parameters
    },
    "nbody": {
        "params": [""],  # No parameters
    },
    "qap": {
        "params": ["problems/chr10a.dat", "problems/chr12a.dat"],
        "param_labels": ["chr10a", "chr12a"],
    },
}


# Run benchmarks and collect data
def run_benchmarks():
    for name, config in BENCHMARKS.items():
        print(f"\nRunning {name} benchmark...")

        params = config["params"]
        if "param_labels" in config:
            param_labels = config["param_labels"]
        else:
            param_labels = params

        # Create CSV file for results
        results_file = RESULTS_DIR / f"{name}_results.csv"
        with open(results_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "param",
                    "repetition",
                    "real_time",
                    "user_time",
                    "sys_time",
                    "max_memory",
                    "real_time_mean",
                    "user_time_mean",
                    "sys_time_mean",
                    "max_memory_mean",
                ]
            )

        # Dictionary to store summary data
        summary_data = {}

        for i, (param, label) in enumerate(zip(params, param_labels)):
            print(f"  Running with parameter: {param if param else 'none'}")

            # Lists to store results for this parameter
            real_times = []
            user_times = []
            sys_times = []
            max_memories = []

            for rep in range(REPETITIONS):
                print(f"    Repetition {rep+1}/{REPETITIONS}")

                # Prepare the command
                if param:
                    cmd = (
                        f"/usr/bin/time -f '%e,%U,%S,%M' {BUILD_DIR}/{name} {param}"
                    )
                else:
                    cmd = f"/usr/bin/time -f '%e,%U,%S,%M' {BUILD_DIR}/{name}"

                # Run the command
                process = subprocess.run(
                    cmd,
                    shell=True,
                    stderr=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    text=True,
                )

                # Extract metrics from stderr (time output)
                time_output = process.stderr.strip().split("\n")[-1]
                real_time, user_time, sys_time, max_memory = map(
                    float, time_output.split(",")
                )

                # Add to lists for summary statistics
                real_times.append(real_time)
                user_times.append(user_time)
                sys_times.append(sys_time)
                max_memories.append(max_memory)

                # Add a small delay between runs
                time.sleep(1)

            # Calculate summary statistics
            real_time_mean = statistics.mean(real_times)
            user_time_mean = statistics.mean(user_times)
            sys_time_mean = statistics.mean(sys_times)
            max_memory_mean = statistics.mean(max_memories)

            summary_data[label] = {
                "real_time": {
                    "mean": real_time_mean,
                    "std": statistics.stdev(real_times)
                    if len(real_times) > 1
                    else 0,
                    "min": min(real_times),
                    "max": max(real_times),
                },
                "user_time": {
                    "mean": user_time_mean,
                    "std": statistics.stdev(user_times)
                    if len(user_times) > 1
                    else 0,
                },
                "sys_time": {
                    "mean": sys_time_mean,
                    "std": statistics.stdev(sys_times)
                    if len(sys_times) > 1
                    else 0,
                },
                "max_memory": {
                    "mean": max_memory_mean,
                    "std": statistics.stdev(max_memories)
                    if len(max_memories) > 1
                    else 0,
                    "min": min(max_memories),
                    "max": max(max_memories),
                },
            }

            # Store the results, including the means, in the CSV
            for rep in range(REPETITIONS):
                with open(results_file, "a", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(
                        [
                            label,
                            rep + 1,
                            real_times[rep],
                            user_times[rep],
                            sys_times[rep],
                            max_memories[rep],
                            real_time_mean,
                            user_time_mean,
                            sys_time_mean,
                            max_memory_mean,
                        ]
                    )

        # Save summary to a text file
        with open(RESULTS_DIR / f"{name}_summary.txt", "w") as f:
            f.write(f"Summary for {name}\n")
            f.write("=" * 80 + "\n\n")

            for param, stats in summary_data.items():
                f.write(f"Parameter: {param}\n")
                f.write("-" * 40 + "\n")
                f.write(
                    f"Real Time (s): {stats['real_time']['mean']:.3f} ± {stats['real_time']['std']:.3f}\n"
                )
                f.write(
                    f"User Time (s): {stats['user_time']['mean']:.3f} ± {stats['user_time']['std']:.3f}\n"
                )
                f.write(
                    f"System Time (s): {stats['sys_time']['mean']:.3f} ± {stats['sys_time']['std']:.3f}\n"
                )
                f.write(
                    f"Max Memory (KB): {stats['max_memory']['mean']:.1f} ± {stats['max_memory']['std']:.1f}\n\n"
                )

        # Also save as JSON for easier parsing
        with open(RESULTS_DIR / f"{name}_summary.json", "w") as f:
            json.dump(summary_data, f, indent=2)



def main():
    # Print hostname and time for SLURM job identification
    hostname = subprocess.check_output("hostname", shell=True).decode().strip()
    print(f"Running on host: {hostname}")
    print(f"Start time: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Build the programs
    build_programs()

    # Run benchmarks and collect data
    run_benchmarks()

    print(f"\nBenchmarking complete. Results saved to {RESULTS_DIR}")
    print(f"End time: {time.strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
