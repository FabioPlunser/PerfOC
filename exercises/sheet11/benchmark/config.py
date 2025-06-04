from pathlib import Path

PROGRAMS = [
    "delannoy",
    "delannoy_memo",
    "delannoy_tabulate",
]

# N values for D(N,N)
# Max N in DELANNOY_RESULTS is 22.
# Original 'delannoy' will be very slow for N > 15.
N_VALUES = [5, 8, 10, 12, 15, 18, 20, 21, 22]

# SLURM configuration
SLURM_PARTITION = "lva"
SLURM_CPUS_PER_TASK = 4  # As per user's original config
SLURM_MEMORY = "16G"  # As per user's original config
SLURM_TIME_LIMIT = "00:30:00"  # 30 minutes
NUM_REPETITIONS = 10  # As per user's original config

# Plotting configuration
PLOT_FORMAT = "png"
PLOT_DPI = 300
PLOT_STYLE = "seaborn-v0_8-whitegrid"

# Output directory structure
BASE_OUTPUT_DIR = Path(
    "/Users/fabioplunser/Nextcloud/Uni/7.Semester/PerfOC/exercises/sheet11/benchmark"
)
C_SOURCE_DIR = Path(
    "/Users/fabioplunser/Nextcloud/Uni/7.Semester/PerfOC/exercises/sheet11/src"
)
BIN_DIR = BASE_OUTPUT_DIR / "bin"
SLURM_SCRIPTS_DIR = BASE_OUTPUT_DIR / "slurm_scripts"
SLURM_LOGS_DIR = BASE_OUTPUT_DIR / "slurm_logs"
RESULTS_FILE = BASE_OUTPUT_DIR / "results" / "delannoy_results.csv"
PLOTS_DIR = BASE_OUTPUT_DIR / "plots"
TABLES_DIR = BASE_OUTPUT_DIR / "tables"
REPORT_FILE = TABLES_DIR / "delannoy_benchmark_report.md"

# Ensure base output directories exist
RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
BIN_DIR.mkdir(parents=True, exist_ok=True)
SLURM_SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
SLURM_LOGS_DIR.mkdir(parents=True, exist_ok=True)
PLOTS_DIR.mkdir(parents=True, exist_ok=True)
TABLES_DIR.mkdir(parents=True, exist_ok=True)
