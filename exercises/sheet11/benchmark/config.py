from pathlib import Path

PROGRAMS = [
    "delannoy",
    "delannoy_memo",
    "delannoy_tab",
]

PROGRAM_N_VALUES = {
    "delannoy":          [5, 8, 10, 12, 14],  
    "delannoy_memo":     [5, 8, 10, 12, 14, 15, 18, 20, 21, 22],
    "delannoy_tab": [5, 8, 10, 12, 14, 15, 18, 20, 21, 22],
}

SLURM_PARTITION = "lva"
SLURM_CPUS_PER_TASK = 4  
SLURM_MEMORY = "16G"  
SLURM_TIME_LIMIT = "00:60:00"  
NUM_REPETITIONS = 5

PLOT_FORMAT = "png"
PLOT_DPI = 300
PLOT_STYLE = "seaborn-v0_8-whitegrid"

BASE_OUTPUT_DIR = Path(
    '/scratch/cb761223/sheet11/benchmark'
)
C_SOURCE_DIR = Path(
    "/scratch/cb761223/sheet11/src"
)
BIN_DIR = BASE_OUTPUT_DIR / "bin"
SLURM_SCRIPTS_DIR = BASE_OUTPUT_DIR / "slurm_scripts"
SLURM_LOGS_DIR = BASE_OUTPUT_DIR / "slurm_logs"
RESULTS_FILE = BASE_OUTPUT_DIR / "results" / "delannoy_results.csv"
PLOTS_DIR = BASE_OUTPUT_DIR / "plots"
TABLES_DIR = BASE_OUTPUT_DIR / "tables"
REPORT_FILE = TABLES_DIR / "delannoy_benchmark_report.md"


