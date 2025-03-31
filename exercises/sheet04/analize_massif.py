#!/usr/bin/env python3

import re
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import sys
import io  # Needed for creating the markdown string

# --- Configuration ---
# *** IMPORTANT: Set this to the correct path where your .log files are ***
SLURM_LOGS_DIR = Path(
    "/scratch/cb761223/exercises/sheet04/slurm_logs"
)
# Output PNG plot file with high DPI settings
OUTPUT_PLOT_FILE = Path(
    "/scratch/cb761223/exercises/sheet04/massif_time_perturbation_high_dpi.png"
)
# Output Markdown file (set to None to only print to console)
OUTPUT_MARKDOWN_FILE = Path(
    "/scratch/cb761223/exercises/sheet04/results_summary.md"
)

# Regex to parse filenames (adjust if your naming changes)
FILENAME_REGEX = re.compile(
    r"^(npb_bt|ssca2)_([A-Za-z0-9]+)_(baseline|massif)\.log$"
)

# Regex to find the 'real' time output from the `time` command
TIME_REGEX = re.compile(r"^\s*real\s+(\d+)m([\d.]+)s", re.MULTILINE)


# --- Helper Functions ---

def parse_time_to_seconds(time_str: str) -> float | None:
    """Converts 'XmY.Zs' string to total seconds."""
    match = TIME_REGEX.search(time_str)
    if match:
        try:
            minutes = float(match.group(1))
            seconds = float(match.group(2))
            return (minutes * 60) + seconds
        except ValueError:
            return None
    return None


def extract_time_from_log(log_file: Path) -> float | None:
    """Reads a log file and extracts the 'real' execution time in seconds."""
    if not log_file.is_file():
        print(f"Warning: Log file not found: {log_file}", file=sys.stderr)
        return None
    try:
        content = log_file.read_text()
        return parse_time_to_seconds(content)
    except Exception as e:
        print(
            f"Warning: Error reading or parsing {log_file}: {e}",
            file=sys.stderr,
        )
        return None


def generate_markdown_table(df: pd.DataFrame) -> str:
    """Generates a Markdown table from the processed DataFrame."""
    # Use StringIO to build the table string efficiently
    md_string_io = io.StringIO()

    # Header
    md_string_io.write(
        "| Program | Time (s) | Time with Massif (s) | Overhead (%) | Peak Memory (MiB) | Peak Memory with Massif (MiB) | Overhead (%) | Largest Source |\n"
    )
    # Separator
    md_string_io.write(
        "|---|---|---|---|---|---|---|---|\n"
    )

    # Data Rows
    for index, row in df.iterrows():
        program_id = index # The index is 'full_id'
        baseline_time = row["baseline"]
        massif_time = row["massif"]
        time_overhead = row["time_overhead_percent"]

        # Format numbers to 2 decimal places
        baseline_time_str = f"{baseline_time:.2f}"
        massif_time_str = f"{massif_time:.2f}"
        time_overhead_str = f"{time_overhead:.2f}"

        # Add placeholders for memory columns
        mem_baseline = "---"
        mem_massif = "---"
        mem_overhead = "---"
        largest_source = "---"

        md_string_io.write(
            f"| {program_id} | {baseline_time_str} | {massif_time_str} | {time_overhead_str} | {mem_baseline} | {mem_massif} | {mem_overhead} | {largest_source} |\n"
        )

    return md_string_io.getvalue()


# --- Main Execution ---

if __name__ == "__main__":
    print(f"--- Analyzing Slurm logs in: {SLURM_LOGS_DIR} ---")

    if not SLURM_LOGS_DIR.is_dir():
        print(
            f"ERROR: Log directory not found: {SLURM_LOGS_DIR}",
            file=sys.stderr,
        )
        sys.exit(1)

    results = []
    log_files_found = 0

    # --- Log Parsing ---
    for log_file in SLURM_LOGS_DIR.glob("*.log"):
        log_files_found += 1
        match = FILENAME_REGEX.match(log_file.name)
        if not match:
            print(
                f"Warning: Skipping file with unexpected name: {log_file.name}",
                file=sys.stderr,
            )
            continue

        benchmark_name = match.group(1)
        identifier = match.group(2)
        run_type = match.group(3)
        full_id = f"{benchmark_name}_{identifier}"

        # print(f"Processing: {log_file.name} (Benchmark: {full_id}, Type: {run_type})")
        real_time = extract_time_from_log(log_file)

        if real_time is not None:
            results.append(
                {
                    "full_id": full_id,
                    "benchmark": benchmark_name,
                    "identifier": identifier,
                    "type": run_type,
                    "time_seconds": real_time,
                }
            )
        # else:
            # print(f"  -> Could not extract time.") # Reduce noise

    if not results:
        print(
            "\nERROR: No valid execution times found in any log files.",
            file=sys.stderr,
        )
        if log_files_found == 0:
            print(f"No .log files were found in {SLURM_LOGS_DIR}", file=sys.stderr)
        sys.exit(1)

    # --- Data Preparation ---
    df = pd.DataFrame(results)
    # print("\n--- Extracted Data ---")
    # print(df) # Can be verbose

    try:
        df_pivot = df.pivot_table(
            index="full_id", columns="type", values="time_seconds"
        )
    except Exception as e:
        print(
            f"\nERROR: Could not pivot data. Do you have matching baseline/massif pairs? Error: {e}",
            file=sys.stderr,
        )
        print("DataFrame before pivot attempt:")
        print(df)
        sys.exit(1)

    missing_cols = []
    if 'baseline' not in df_pivot.columns: missing_cols.append('baseline')
    if 'massif' not in df_pivot.columns: missing_cols.append('massif')
    if missing_cols:
        print(f"\nERROR: Missing required run types in data: {', '.join(missing_cols)}", file=sys.stderr)
        print("Pivot table created:")
        print(df_pivot)
        sys.exit(1)

    original_rows = len(df_pivot)
    df_pivot.dropna(subset=["baseline", "massif"], inplace=True)
    dropped_rows = original_rows - len(df_pivot)
    if dropped_rows > 0:
        print(f"\nWarning: Dropped {dropped_rows} rows due to missing baseline or massif times.")

    if df_pivot.empty:
        print("\nERROR: No complete baseline/massif pairs found after processing.", file=sys.stderr)
        sys.exit(1)

    # --- Calculate Time Overhead ---
    # Avoid division by zero if baseline time is somehow 0
    df_pivot["time_overhead_percent"] = df_pivot.apply(
        lambda row: (
            ((row["massif"] - row["baseline"]) / row["baseline"]) * 100
            if row["baseline"] > 0
            else 0
        ),
        axis=1,
    )

    print("\n--- Processed Data with Overhead ---")
    print(df_pivot)

    # --- Generate and Output Markdown Table ---
    print("\n--- Generating Markdown Summary Table ---")
    markdown_table = generate_markdown_table(df_pivot)
    print(markdown_table) # Print to console

    if OUTPUT_MARKDOWN_FILE:
        try:
            OUTPUT_MARKDOWN_FILE.write_text(markdown_table)
            print(f"Markdown table saved successfully to {OUTPUT_MARKDOWN_FILE}")
        except Exception as e:
            print(f"ERROR: Failed to save markdown table: {e}", file=sys.stderr)


    # --- Plotting with Matplotlib/Pyplot ---
    print(f"\n--- Generating Plot: {OUTPUT_PLOT_FILE} ---")

    plt.rcParams['figure.dpi'] = 150
    fig, ax = plt.subplots(figsize=(14, 8))

    fig.set_facecolor('white')

    # Plot only baseline and massif times
    df_pivot[["baseline", "massif"]].plot(
        kind="bar",
        ax=ax,
        color=['blue', 'red'],
        rot=45,
        width=0.8
    )

    ax.set_title("Execution Time Comparison: Baseline vs. Massif")
    ax.set_xlabel("Benchmark and Identifier/Scale")
    ax.set_ylabel("Execution Time (seconds)")
    ax.grid(axis="y", linestyle="--", alpha=0.7, color='grey')
    ax.legend(title="Run Type")

    plt.tight_layout()

    try:
        plt.savefig(
            OUTPUT_PLOT_FILE,
            format='png',
            dpi=300,
            facecolor=fig.get_facecolor()
            )
        print(f"Plot saved successfully to {OUTPUT_PLOT_FILE}")
    except Exception as e:
        print(f"ERROR: Failed to save plot: {e}", file=sys.stderr)

    plt.close(fig)

    print("\n--- Analysis Complete ---")
