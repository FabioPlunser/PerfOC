#!/usr/bin/env python3

import re
import pandas as pd
import matplotlib.pyplot as plt # Import pyplot
from pathlib import Path
import sys

# --- Configuration ---
# *** IMPORTANT: Set this to the correct path where your .log files are ***
SLURM_LOGS_DIR = Path(
    "/scratch/cb761223/exercises/sheet04/slurm_logs"
)
# Output SVG plot file with high DPI settings
OUTPUT_PLOT_FILE = Path(
    "/scratch/cb761223/exercises/sheet04/massif_time_perturbation_high_dpi.png"
)

# Regex to parse filenames (adjust if your naming changes)
FILENAME_REGEX = re.compile(
    r"^(npb_bt|ssca2)_([A-Za-z0-9]+)_(baseline|massif)\.log$"
)

# Regex to find the 'real' time output from the `time` command
TIME_REGEX = re.compile(r"^\s*real\s+(\d+)m([\d.]+)s", re.MULTILINE)


# --- Helper Functions --- (Identical to previous script)

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

    # --- Log Parsing (Identical to previous script) ---
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

        print(f"Processing: {log_file.name} (Benchmark: {full_id}, Type: {run_type})")
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
        else:
            print(f"  -> Could not extract time.")

    if not results:
        print(
            "\nERROR: No valid execution times found in any log files.",
            file=sys.stderr,
        )
        if log_files_found == 0:
            print(f"No .log files were found in {SLURM_LOGS_DIR}", file=sys.stderr)
        sys.exit(1)

    # --- Data Preparation (Identical to previous script) ---
    df = pd.DataFrame(results)
    print("\n--- Extracted Data ---")
    print(df)

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

    print("\n--- Data for Plotting ---")
    print(df_pivot)

    # --- Plotting with Matplotlib/Pyplot ---
    print(f"\n--- Generating Plot: {OUTPUT_PLOT_FILE} ---")

    # Set a higher DPI value for better quality/resolution feel in SVG
    # Increase figure size for better layout with potentially many bars
    plt.rcParams['figure.dpi'] = 150 # Affects default sizing, good starting point
    fig, ax = plt.subplots(figsize=(14, 8)) # Create figure and axes explicitly

    # Set background color for the figure (area outside the plot axes)
    fig.set_facecolor('white')
    # Optionally set axes background too, though usually figure is enough
    # ax.set_facecolor('white')

    # Plot the bars using blue for baseline and red for massif
    df_pivot[["baseline", "massif"]].plot(
        kind="bar",
        ax=ax, # Plot on the created axes
        color=['blue', 'red'], # Specify colors for columns
        rot=45, # Rotate x-axis labels
        width=0.8 # Adjust bar width if needed
    )

    # Customize the plot
    ax.set_title("Execution Time Comparison: Baseline vs. Massif (High DPI SVG)")
    ax.set_xlabel("Benchmark and Identifier/Scale")
    ax.set_ylabel("Execution Time (seconds)")
    ax.grid(axis="y", linestyle="--", alpha=0.7, color='grey') # Grey grid lines
    ax.legend(title="Run Type")

    # Adjust layout to prevent labels overlapping
    plt.tight_layout()

    try:
        # Save as SVG, explicitly setting DPI and ensuring background color is saved
        plt.savefig(
            OUTPUT_PLOT_FILE,
            format='png',
            dpi=300, # Embed higher DPI hint in SVG if renderer uses it
            facecolor=fig.get_facecolor() # Ensure white background is saved
            )
        print(f"Plot saved successfully to {OUTPUT_PLOT_FILE}")
    except Exception as e:
        print(f"ERROR: Failed to save plot: {e}", file=sys.stderr)

    # Close the plot figure to free memory
    plt.close(fig)

    # Optionally display the plot if running in a graphical environment
    # plt.show() # This would require a different backend usually

    print("\n--- Analysis Complete ---")
