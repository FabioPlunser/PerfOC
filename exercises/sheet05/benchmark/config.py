# config.py
from pathlib import Path

# --- Default Source Code Locations (REMOVED) ---
# DEFAULT_SMALL_SAMPLES_DIR = Path("./small_samples")
# DEFAULT_LARGER_SAMPLES_DIR = Path("./larger_samples")
DEFAULT_PROGRAM_CONFIG_FILE = Path("./programs.json") # Default location for JSON

# --- Output Subdirectories (Relative to base output dir specified in CLI) ---
# (BUILD_SUBDIR, SLURM_SCRIPTS_SUBDIR, etc. remain the same)
BUILD_SUBDIR = "build"
SLURM_SCRIPTS_SUBDIR = "slurm_scripts"
SLURM_LOGS_SUBDIR = "slurm_logs"
RESULTS_SUBDIR = "results"
PLOTS_SUBDIR = "plots"

# --- Slurm Configuration ---
# (SLURM_PARTITION, etc. remain the same)
SLURM_PARTITION = "lva"
SLURM_NTASKS = 1
SLURM_NODES = 1
SLURM_CPUS_PER_TASK = 1
SLURM_TIME = "00:30:00"

# --- GCC, CMake, Ninja Modules ---
# (MODULES_TO_LOAD, CC, CXX remain the same)
MODULES_TO_LOAD = [
    "gcc/12.2.0-gcc-8.5.0-p4pe45v",
    "cmake/3.24.3-gcc-8.5.0-svdlhox",
    "ninja/1.11.1-python-3.10.8-gcc-8.5.0-2oc4wj6",
]
CC = "gcc"
CXX = "g++"

# --- Default Benchmarking Parameters ---
# (DEFAULT_OPTIMIZATION_LEVELS, DEFAULT_NUM_RUNS remain the same)
DEFAULT_OPTIMIZATION_LEVELS = ["O0", "O1", "O2", "O3", "Os", "Ofast"]
DEFAULT_NUM_RUNS = 5

# --- Flags for Exercise B ---
# (O2_O3_DIFF_FLAGS dictionary remains the same)
O2_O3_DIFF_FLAGS = {
    "fgcse-after-reload": (0, 1),
    "finline-functions": (0, 1),
    "fipa-cp-clone": (0, 1),
    "floop-interchange": (0, 1),
    "floop-unroll-and-jam": (0, 1),
    "fpeel-loops": (0, 1),            
    "fpredictive-commoning": (0, 1),
    "fsplit-loops": (0, 1),
    "fsplit-paths": (0, 1),            
    "ftree-loop-distribute-patterns": (0, 1),
    "ftree-loop-distribution": (0, 1),
    "ftree-loop-vectorize": (0, 1),
    "ftree-partial-pre": (0, 1),
    "ftree-slp-vectorize": (0, 1),
    "funswitch-loops": (0, 1),
}
