#!/usr/bin/env python3

from pathlib import Path

# Data structures to benchmark
DATA_STRUCTURES = [
    "array",
    "linkedlist_seq",
    "linkedlist_rand",
    "unrolled_linkedlist_8",
    "unrolled_linkedlist_16",
    "unrolled_linkedlist_32",
    "unrolled_linkedlist_64",
    "unrolled_linkedlist_128",
    "unrolled_linkedlist_256",
    "tiered_array_8",
    "tiered_array_16",
    "tiered_array_32",
    "tiered_array_64",
    "tiered_array_128",
    "tiered_array_256",
]

# Benchmark parameters - RATIO represents ins_del ratio
RATIOS = [0.0, 0.01, 0.10, 0.50]  # ins_del ratios
ELEMENT_SIZES = [8, 512, 8 * 1024 * 1024]
NUM_ELEMENTS = [10, 1000, 100000, 10000000]
TEST_DURATION = 3.0  # seconds
RANDOM_ACCESS = [0, 1]

# SLURM configuration
SLURM_PARTITION = "lva"
SLURM_CPUS_PER_TASK = 4
SLURM_MEMORY = "16G"
SLURM_TIME_LIMIT = "00:05:00"  # Increased for longer test duration
NUM_REPETITIONS = 3

# Plotting configuration
PLOT_FORMAT = "png"  # or "svg"
PLOT_DPI = 300
PLOT_STYLE = "seaborn-v0_8-whitegrid"
