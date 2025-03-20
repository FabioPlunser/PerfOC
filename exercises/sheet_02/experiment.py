#!/usr/bin/env python3

import os
import subprocess
import csv
import statistics
import math
import numpy as np
from pathlib import Path
import json
import time
import matplotlib.pyplot as plt
import pandas as pd
import random
import threading
import scipy.stats as stats
import tempfile
import shutil
import sys

# Set up directories with the provided root directory
# ROOT_DIR = Path("/scratch/cb761223")
ROOT_DIR = Path("/Users/fabioplunser/Nextcloud/Uni/7.Semester/POC/")
SCRIPT_DIR = ROOT_DIR / "perf-oriented-dev/small_samples/"
CURRENT_DIR = ROOT_DIR / "exercises/sheet_02/"
TOOLS_DIR = ROOT_DIR / "perf-oriented-dev/tools/"

BUILD_DIR = SCRIPT_DIR / "build"
RESULTS_DIR = CURRENT_DIR / "experiment_results"
LOCAL_FS_DIR = Path(tempfile.mkdtemp(prefix="perf_benchmark_"))


# Create directories if they don't exist
BUILD_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)

# Configuration
CONFIDENCE_LEVEL = 0.95  # 95% confidence interval
MAX_REPETITIONS = 20  # Maximum number of repetitions
MIN_REPETITIONS = 3  # Minimum number of repetitions
TARGET_MARGIN_OF_ERROR = 0.05  # Target margin of error (5%)

# Define load scenarios
LOAD_SCENARIOS = ["no_load", "cpu_load", "io_load"]

# Define compiler options for specific benchmarks
COMPILER_OPTIONS = {
    "nbody": [
        {"define": "N=1000", "label": "N1000"},
        {"define": "N=2000", "label": "N2000"},
        {"define": "N=5000", "label": "N5000"},
    ],
    # Add other benchmarks with compiler options as needed
}


# Build the programs with specific compiler options
def build_programs():
    print("Building programs...")
    os.chdir(BUILD_DIR)

    # Run CMake if not already configured
    if not (BUILD_DIR / "build.ninja").exists():
        subprocess.run(
            ["cmake", "..", "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release"],
            check=True,
        )

    # Build all programs with default options
    subprocess.run(["ninja"], check=True)

    # Build programs with specific compiler options
    for program, options_list in COMPILER_OPTIONS.items():
        for options in options_list:
            define_option = options["define"]
            label = options["label"]

            # Create a custom build target for this configuration
            custom_target = f"{program}_{label}"

            print(f"Building {program} with option: {define_option}")

            # Compile the program with the specific define
            compile_cmd = f"c++ -O3 -DCMAKE_BUILD_TYPE=Release -D{define_option} {SCRIPT_DIR}/{program}.cpp -o {BUILD_DIR}/{custom_target}"

            try:
                subprocess.run(compile_cmd, shell=True, check=True)
                print(f"Successfully built {custom_target}")
            except subprocess.CalledProcessError as e:
                print(f"Failed to build {custom_target}: {e}")

    # Also build loadgen
    os.chdir(TOOLS_DIR)
    if not (TOOLS_DIR / "build/loadgen").exists():
        os.makedirs(TOOLS_DIR / "build", exist_ok=True)
        os.chdir(TOOLS_DIR / "build")
        subprocess.run(
            ["cmake", "..", "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release"],
            check=True,
        )
        subprocess.run(["ninja"], check=True)

    os.chdir(SCRIPT_DIR)
    print("Build complete.")


# Define benchmark configurations
BENCHMARKS = {
    "delannoy": {
        "params": ["10", "14"],
        "io_bound": False,
    },
    "file_generator": {
        "params": [
            "5 100 1024 10240 1234",
            "10 200 1024 102400 1234",
        ],
        "param_labels": ["small", "medium"],
        "io_bound": True,
    },
    "find_largest_file": {
        "params": [""],
        "io_bound": True,
    },
    "matrix_mult": {
        "params": [""],
        "io_bound": False,
    },
    "nbody": {
        "params": [""],
        "io_bound": False,
        "compiler_options": True,  # Flag to indicate this benchmark uses compiler options
    },
    "qap": {
        "params": ["problems/chr10a.dat", "problems/chr12a.dat"],
        "param_labels": ["chr10a", "chr12a"],
        "io_bound": False,
    },
}


# CPU Load Generator
def start_cpu_load():
    """Start CPU load using loadgen"""
    print("Starting CPU load generator...")
    loadgen_path = TOOLS_DIR / "build/loadgen"
    profile_path = TOOLS_DIR / "workstation/sys_load_profile_workstation_excerpt.txt"

    # Kill any existing loadgen processes
    subprocess.run("killall loadgen &> /dev/null || true", shell=True)

    # Start multiple loadgen instances
    for _ in range(6):  # Start 6 instances as in the example script
        subprocess.Popen(
            f"{loadgen_path} mc3 {profile_path} > /dev/null 2>&1", shell=True
        )

    # Give loadgen time to start
    time.sleep(2)
    print("CPU load generator started")


def stop_cpu_load():
    """Stop CPU load by killing loadgen processes"""
    print("Stopping CPU load generator...")
    subprocess.run("killall loadgen &> /dev/null || true", shell=True)
    print("CPU load generator stopped")


# I/O Load Generator using external script
def start_io_load():
    """Start I/O load using the external ioLoadGenerator.py script"""
    print("Starting I/O load generator...")

    # Path to the I/O load generator script
    io_load_script = CURRENT_DIR / "ioLoadGenerator.py"

    # Start the I/O load generator in the background
    subprocess.Popen(
        f"python3 {io_load_script} generate --dir {LOCAL_FS_DIR} --intensity 4 --duration 3600 > /dev/null 2>&1",
        shell=True,
    )

    # Give it time to start
    time.sleep(2)
    print("I/O load generator started")


def stop_io_load():
    """Stop I/O load by killing the ioLoadGenerator.py process"""
    print("Stopping I/O load generator...")
    subprocess.run("pkill -f 'python3.*ioLoadGenerator.py' || true", shell=True)
    print("I/O load generator stopped")


# Calculate confidence interval
def calculate_confidence_interval(data, confidence=0.95):
    n = len(data)
    mean = statistics.mean(data)
    if n <= 1:
        return mean, 0, 0

    std_err = statistics.stdev(data) / math.sqrt(n)
    h = std_err * stats.t.ppf((1 + confidence) / 2, n - 1)

    return mean, h, h / mean  # mean, half-width, relative error


# Run benchmarks with dynamic repetitions
def run_benchmarks():
    all_results = {}

    for scenario in LOAD_SCENARIOS:
        print(f"\n=== Running benchmarks with {scenario} ===")
        all_results[scenario] = {}

        for name, config in BENCHMARKS.items():
            print(f"\nRunning {name} benchmark...")
            all_results[scenario][name] = {}

            # Skip I/O benchmarks for CPU load and vice versa to save time
            if scenario == "cpu_load" and config.get("io_bound", False):
                print(f"  Skipping I/O-bound benchmark {name} for CPU load scenario")
                continue

            if scenario == "io_load" and not config.get("io_bound", False):
                print(f"  Skipping CPU-bound benchmark {name} for I/O load scenario")
                continue

            # Check if this benchmark uses compiler options
            if config.get("compiler_options", False) and name in COMPILER_OPTIONS:
                # Use compiler options instead of command-line parameters
                param_configs = []
                for option in COMPILER_OPTIONS[name]:
                    param_configs.append(
                        {
                            "executable": f"{name}_{option['label']}",
                            "param": "",
                            "label": option["label"],
                        }
                    )
            else:
                # Use regular command-line parameters
                params = config["params"]
                if "param_labels" in config:
                    param_labels = config["param_labels"]
                else:
                    param_labels = params

                param_configs = []
                for param, label in zip(params, param_labels):
                    param_configs.append(
                        {"executable": name, "param": param, "label": label}
                    )

            # Create CSV file for results
            results_file = RESULTS_DIR / f"{name}_{scenario}_results.csv"
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
                        "real_time_ci",
                        "user_time_mean",
                        "sys_time_mean",
                        "max_memory_mean",
                    ]
                )

            # Start appropriate load generator
            try:
                if scenario == "cpu_load":
                    start_cpu_load()
                elif scenario == "io_load":
                    start_io_load()

                # Dictionary to store summary data
                summary_data = {}

                for param_config in param_configs:
                    executable = param_config["executable"]
                    param = param_config["param"]
                    label = param_config["label"]

                    print(
                        f"  Running {executable} with parameter: {param if param else 'none'}"
                    )

                    # Lists to store results for this parameter
                    real_times = []
                    user_times = []
                    sys_times = []
                    max_memories = []

                    # Dynamic repetitions
                    rep = 0
                    relative_error = float("inf")

                    while rep < MIN_REPETITIONS or (
                        relative_error > TARGET_MARGIN_OF_ERROR
                        and rep < MAX_REPETITIONS
                    ):
                        rep += 1
                        print(
                            f"    Repetition {rep}/{MAX_REPETITIONS} (target error: {TARGET_MARGIN_OF_ERROR:.2%})"
                        )

                        # Prepare the command
                        if param:
                            cmd = f"/usr/bin/time -f '%e,%U,%S,%M' {BUILD_DIR}/{executable} {param}"
                        else:
                            cmd = f"/usr/bin/time -f '%e,%U,%S,%M' {BUILD_DIR}/{executable}"

                        # For I/O benchmarks, use local filesystem
                        if config.get("io_bound", False):
                            os.chdir(LOCAL_FS_DIR)

                        # Run the command
                        process = subprocess.run(
                            cmd,
                            shell=True,
                            stderr=subprocess.PIPE,
                            stdout=subprocess.PIPE,
                            text=True,
                        )

                        # Return to original directory
                        if config.get("io_bound", False):
                            os.chdir(SCRIPT_DIR)

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

                        # Calculate confidence interval for real_time
                        if len(real_times) >= 2:
                            _, _, relative_error = calculate_confidence_interval(
                                real_times, CONFIDENCE_LEVEL
                            )
                            print(f"      Current relative error: {relative_error:.2%}")

                        # Add a small delay between runs
                        time.sleep(1)

                    # Calculate final statistics
                    real_time_mean, real_time_ci, _ = calculate_confidence_interval(
                        real_times, CONFIDENCE_LEVEL
                    )
                    user_time_mean = statistics.mean(user_times)
                    sys_time_mean = statistics.mean(sys_times)
                    max_memory_mean = statistics.mean(max_memories)

                    summary_data[label] = {
                        "real_time": {
                            "mean": real_time_mean,
                            "ci": real_time_ci,
                            "std": (
                                statistics.stdev(real_times)
                                if len(real_times) > 1
                                else 0
                            ),
                            "min": min(real_times),
                            "max": max(real_times),
                            "values": real_times,
                        },
                        "user_time": {
                            "mean": user_time_mean,
                            "std": (
                                statistics.stdev(user_times)
                                if len(user_times) > 1
                                else 0
                            ),
                            "values": user_times,
                        },
                        "sys_time": {
                            "mean": sys_time_mean,
                            "std": (
                                statistics.stdev(sys_times) if len(sys_times) > 1 else 0
                            ),
                            "values": sys_times,
                        },
                        "max_memory": {
                            "mean": max_memory_mean,
                            "std": (
                                statistics.stdev(max_memories)
                                if len(max_memories) > 1
                                else 0
                            ),
                            "min": min(max_memories),
                            "max": max(max_memories),
                            "values": max_memories,
                        },
                        "repetitions": len(real_times),
                    }

                    # Store the results in the CSV
                    for idx in range(len(real_times)):
                        with open(results_file, "a", newline="") as f:
                            writer = csv.writer(f)
                            writer.writerow(
                                [
                                    label,
                                    idx + 1,
                                    real_times[idx],
                                    user_times[idx],
                                    sys_times[idx],
                                    max_memories[idx],
                                    real_time_mean,
                                    real_time_ci,
                                    user_time_mean,
                                    sys_time_mean,
                                    max_memory_mean,
                                ]
                            )

                # Save summary to a text file
                with open(RESULTS_DIR / f"{name}_{scenario}_summary.txt", "w") as f:
                    f.write(f"Summary for {name} with {scenario}\n")
                    f.write("=" * 80 + "\n\n")

                    for param, stats in summary_data.items():
                        f.write(f"Parameter: {param}\n")
                        f.write("-" * 40 + "\n")
                        f.write(f"Repetitions: {stats['repetitions']}\n")
                        f.write(
                            f"Real Time (s): {stats['real_time']['mean']:.3f} ± {stats['real_time']['ci']:.3f} "
                            f"({stats['real_time']['ci']/stats['real_time']['mean']*100:.1f}% CI)\n"
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
                with open(RESULTS_DIR / f"{name}_{scenario}_summary.json", "w") as f:
                    json.dump(summary_data, f, indent=2)

                all_results[scenario][name] = summary_data

            finally:
                # Stop load generators
                if scenario == "cpu_load":
                    stop_cpu_load()
                elif scenario == "io_load":
                    stop_io_load()

    return all_results


# Generate graphs
def generate_graphs(all_results):
    print("\nGenerating graphs...")

    # Create a directory for graphs
    graphs_dir = RESULTS_DIR / "graphs"
    graphs_dir.mkdir(exist_ok=True)

    # 1. Comparison of real time across different load scenarios for each benchmark
    for name in BENCHMARKS.keys():
        # Skip if benchmark wasn't run in all scenarios
        scenarios_present = [
            scenario for scenario in LOAD_SCENARIOS if name in all_results[scenario]
        ]
        if not scenarios_present:
            continue

        plt.figure(figsize=(12, 6))

        # Get all parameter labels for this benchmark
        all_params = set()
        for scenario in scenarios_present:
            all_params.update(all_results[scenario][name].keys())

        all_params = sorted(list(all_params))

        # Set up bar positions
        bar_width = 0.8 / len(scenarios_present)
        index = np.arange(len(all_params))

        # Plot bars for each scenario
        for i, scenario in enumerate(scenarios_present):
            means = []
            errors = []

            for param in all_params:
                if param in all_results[scenario][name]:
                    means.append(
                        all_results[scenario][name][param]["real_time"]["mean"]
                    )
                    errors.append(all_results[scenario][name][param]["real_time"]["ci"])
                else:
                    means.append(0)
                    errors.append(0)

            plt.bar(
                index + i * bar_width - 0.4 + bar_width / 2,
                means,
                bar_width,
                yerr=errors,
                label=scenario.replace("_", " ").title(),
                capsize=5,
            )

        plt.xlabel("Parameters")
        plt.ylabel("Real Time (s)")
        plt.title(f"Real Time Comparison for {name} Across Load Scenarios")
        plt.xticks(index, all_params)
        plt.legend()
        plt.tight_layout()
        plt.savefig(graphs_dir / f"{name}_real_time_comparison.png")
        plt.close()

        # 2. Memory usage comparison
        plt.figure(figsize=(12, 6))

        # Plot bars for each scenario
        for i, scenario in enumerate(scenarios_present):
            means = []
            errors = []

            for param in all_params:
                if param in all_results[scenario][name]:
                    means.append(
                        all_results[scenario][name][param]["max_memory"]["mean"] / 1024
                    )  # Convert to MB
                    errors.append(
                        all_results[scenario][name][param]["max_memory"]["std"] / 1024
                    )
                else:
                    means.append(0)
                    errors.append(0)

            plt.bar(
                index + i * bar_width - 0.4 + bar_width / 2,
                means,
                bar_width,
                yerr=errors,
                label=scenario.replace("_", " ").title(),
                capsize=5,
            )

        plt.xlabel("Parameters")
        plt.ylabel("Memory Usage (MB)")
        plt.title(f"Memory Usage Comparison for {name} Across Load Scenarios")
        plt.xticks(index, all_params)
        plt.legend()
        plt.tight_layout()
        plt.savefig(graphs_dir / f"{name}_memory_comparison.png")
        plt.close()

    # 3. Create a summary graph showing the impact of load on different benchmarks
    plt.figure(figsize=(14, 8))

    # Collect data for all benchmarks that have results in relevant scenarios
    benchmark_names = []
    no_load_times = []
    cpu_load_times = []
    io_load_times = []

    for name, config in BENCHMARKS.items():
        # Skip if no results for this benchmark
        if name not in all_results["no_load"]:
            continue

        # Use only the first parameter for simplicity
        if len(all_results["no_load"][name]) > 0:
            param = list(all_results["no_load"][name].keys())[0]

            benchmark_names.append(name)
            no_load_times.append(
                all_results["no_load"][name][param]["real_time"]["mean"]
            )

            # Add CPU load time if available
            if (
                "cpu_load" in all_results
                and name in all_results["cpu_load"]
                and param in all_results["cpu_load"][name]
            ):
                cpu_load_times.append(
                    all_results["cpu_load"][name][param]["real_time"]["mean"]
                )
            else:
                cpu_load_times.append(0)

            # Add I/O load time if available
            if (
                "io_load" in all_results
                and name in all_results["io_load"]
                and param in all_results["io_load"][name]
            ):
                io_load_times.append(
                    all_results["io_load"][name][param]["real_time"]["mean"]
                )
            else:
                io_load_times.append(0)

    if benchmark_names:  # Only create graph if we have data
        # Set up bar positions
        bar_width = 0.25
        index = np.arange(len(benchmark_names))

        # Plot bars
        plt.bar(index, no_load_times, bar_width, label="No Load")
        plt.bar(index + bar_width, cpu_load_times, bar_width, label="CPU Load")
        plt.bar(index + 2 * bar_width, io_load_times, bar_width, label="I/O Load")

        plt.xlabel("Benchmark")
        plt.ylabel("Real Time (s)")
        plt.title("Impact of Different Load Types on Benchmark Performance")
        plt.xticks(index + bar_width, benchmark_names)
        plt.legend()
        plt.tight_layout()
        plt.savefig(graphs_dir / "load_impact_summary.png")
        plt.close()

    # 4. Create a graph showing the number of repetitions needed for each benchmark
    plt.figure(figsize=(14, 8))

    # Collect data
    benchmark_names = []
    repetitions = []

    for name in BENCHMARKS.keys():
        if name in all_results["no_load"] and all_results["no_load"][name]:
            # Use the first parameter
            param = list(all_results["no_load"][name].keys())[0]

            benchmark_names.append(name)
            repetitions.append(all_results["no_load"][name][param]["repetitions"])

    if benchmark_names:  # Only create graph if we have data
        # Plot bars
        plt.bar(benchmark_names, repetitions)
        plt.axhline(
            y=MIN_REPETITIONS,
            color="r",
            linestyle="--",
            label=f"Minimum ({MIN_REPETITIONS})",
        )
        plt.axhline(
            y=MAX_REPETITIONS,
            color="g",
            linestyle="--",
            label=f"Maximum ({MAX_REPETITIONS})",
        )

        plt.xlabel("Benchmark")
        plt.ylabel("Number of Repetitions")
        plt.title(
            f"Repetitions Needed to Achieve {CONFIDENCE_LEVEL*100}% Confidence with {TARGET_MARGIN_OF_ERROR*100}% Error"
        )
        plt.legend()
        plt.tight_layout()
        plt.savefig(graphs_dir / "repetitions_needed.png")
        plt.close()

    # 5. For benchmarks with compiler options, create comparison graphs
    for name, options in COMPILER_OPTIONS.items():
        if name in all_results["no_load"]:
            # Create a graph comparing different compiler options
            plt.figure(figsize=(12, 6))

            option_labels = [opt["label"] for opt in options]
            means = []
            errors = []

            for label in option_labels:
                if label in all_results["no_load"][name]:
                    means.append(
                        all_results["no_load"][name][label]["real_time"]["mean"]
                    )
                    errors.append(
                        all_results["no_load"][name][label]["real_time"]["ci"]
                    )
                else:
                    means.append(0)
                    errors.append(0)

            plt.bar(option_labels, means, yerr=errors, capsize=5)
            plt.xlabel("Compiler Options")
            plt.ylabel("Real Time (s)")
            plt.title(f"Performance Impact of Different Compiler Options for {name}")
            plt.tight_layout()
            plt.savefig(graphs_dir / f"{name}_compiler_options_comparison.png")
            plt.close()

    print(f"Graphs saved to {graphs_dir}")


def main():
    # Print hostname and time for SLURM job identification
    hostname = subprocess.check_output("hostname", shell=True).decode().strip()
    print(f"Running on host: {hostname}")
    print(f"Start time: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        # Build the programs
        build_programs()

        # Run benchmarks and collect data
        all_results = run_benchmarks()

        # Generate graphs
        generate_graphs(all_results)

        print(f"\nBenchmarking complete. Results saved to {RESULTS_DIR}")
    finally:
        # Clean up local filesystem directory
        if os.path.exists(LOCAL_FS_DIR):
            shutil.rmtree(LOCAL_FS_DIR)

        # Make sure load generators are stopped
        stop_cpu_load()
        stop_io_load()

    print(f"End time: {time.strftime('%Y-%m-%d %H:%M:%S')}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run benchmarks with different load scenarios"
    )
    parser.add_argument(
        "--root-dir",
        type=str,
        default="/scratch/cb761223",
        help="Root directory for the project (default: /scratch/cb761223)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
