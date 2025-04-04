#!/usr/bin/env python3

import re
import pandas as pd
import numpy as np # Make sure NumPy is imported
import matplotlib.pyplot as plt
from pathlib import Path
import sys
import io
import math
# Removed base64 import as it's no longer needed

# --- Configuration ---
# *** Base directory for the perf analysis outputs ***
PERF_BASE_DIR = Path("/scratch/cb761223/exercises/sheet04/perf") # Corrected path
SLURM_LOGS_DIR = PERF_BASE_DIR / "slurm_logs"
PERF_OUTPUTS_DIR = PERF_BASE_DIR / "perf_outputs"

# Output directory for plots and the final report
REPORT_OUTPUT_DIR = PERF_BASE_DIR / "analysis_report"
REPORT_OUTPUT_DIR.mkdir(exist_ok=True)

# Output files
OUTPUT_TIME_PLOT_FILE = REPORT_OUTPUT_DIR / "perf_time_perturbation.png"
OUTPUT_REL_METRICS_PLOT_FILE = REPORT_OUTPUT_DIR / "relative_metrics_comparison.png"
OUTPUT_MARKDOWN_FILE = REPORT_OUTPUT_DIR / "perf_analysis_summary.md"

# Regex to parse Slurm log filenames
SLURM_FILENAME_REGEX = re.compile(
    r"^(npb_bt|ssca2)_([A-Za-z0-9_.-]+)_(baseline|perf_grp(\d+))\.log$"
)

# Regex to parse perf output filenames
PERF_FILENAME_REGEX = re.compile(
    r"^perf\.out\.(npb_bt|ssca2)_([A-Za-z0-9_.-]+)_perf_grp(\d+)$"
)

# Regex to find the 'real' time output from the `time` command in Slurm logs
TIME_REGEX = re.compile(r"^\s*real\s+(\d+)m([\d.]+)s", re.MULTILINE)

# Regex to extract perf counter values
PERF_COUNTER_REGEX = re.compile(
    r"^\s*([\d,]+)\s+([\w-]+(?:[:\.,]\w+)*)\s*.*?(?:\#.*)?$", re.MULTILINE
)
PERF_NOT_SUPPORTED_REGEX = re.compile(
    r"^\s*<not supported>\s+([\w-]+(?:[:\.,]\w+)*)\s*.*$", re.MULTILINE
)

# Define ALL counters we might be interested in, based on user request
ALL_TARGET_COUNTERS = [
    "L1-dcache-load-misses", "L1-dcache-loads",
    "L1-dcache-prefetch-misses", "L1-dcache-prefetches",
    "L1-dcache-store-misses", "L1-dcache-stores",
    "L1-icache-load-misses", "L1-icache-loads",
    "LLC-load-misses", "LLC-loads",
    "LLC-prefetch-misses", "LLC-prefetches",
    "LLC-store-misses", "LLC-stores",
    "branch-load-misses", "branch-loads",
    "dTLB-load-misses", "dTLB-loads",
    "dTLB-store-misses", "dTLB-stores",
    "iTLB-load-misses", "iTLB-loads",
    "node-load-misses", "node-loads",
    "node-prefetch-misses", "node-prefetches",
    "node-store-misses", "node-stores",
    # Add instructions and cycles if available and needed for CPI etc.
    "instructions", "cycles"
]

# Define the counters needed as denominators for relative metrics calculation
# This helps ensure we check for their existence and non-zero value
REQUIRED_DENOMINATORS = [
    "L1-dcache-loads", "L1-dcache-stores", "L1-dcache-prefetches",
    "L1-icache-loads",
    "LLC-loads", "LLC-stores", "LLC-prefetches",
    "branch-loads",
    "dTLB-loads", "dTLB-stores",
    "iTLB-loads",
    "node-loads", "node-stores", "node-prefetches",
]


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
    """Reads a Slurm log file and extracts the 'real' execution time."""
    if not log_file.is_file():
        print(f"Warning: Slurm log file not found: {log_file}", file=sys.stderr)
        return None
    try:
        content = log_file.read_text()
        return parse_time_to_seconds(content)
    except Exception as e:
        print(f"Warning: Error reading/parsing Slurm log {log_file}: {e}", file=sys.stderr)
        return None

def parse_perf_output(perf_file: Path) -> dict[str, float]:
    """Reads a perf output file and extracts counter values."""
    counters = {}
    if not perf_file.is_file():
        print(f"Warning: Perf output file not found: {perf_file}", file=sys.stderr)
        return counters
    try:
        content = perf_file.read_text()
        # Find numeric values
        for match in PERF_COUNTER_REGEX.finditer(content):
            try:
                value_str = match.group(1).replace(",", "")
                value = float(value_str)
                event = match.group(2).strip()
                # Handle potential suffixes like :u, :k, :ukh etc. by taking base name
                event_base = event.split(':')[0]
                # If the same base event (e.g., cycles) appears multiple times
                # (like cycles:u and cycles:k), sum them up.
                counters[event_base] = counters.get(event_base, 0) + value
            except ValueError:
                print(f"Warning: Could not parse value in {perf_file} for line: {match.group(0)}", file=sys.stderr)
                continue
        # Find <not supported> events and mark them as NaN
        for match in PERF_NOT_SUPPORTED_REGEX.finditer(content):
             event = match.group(1).strip()
             event_base = event.split(':')[0]
             if event_base not in counters: # Only mark as NaN if no numeric value was found
                 counters[event_base] = math.nan

    except Exception as e:
        print(f"Warning: Error reading/parsing perf output {perf_file}: {e}", file=sys.stderr)
    return counters

def calculate_relative_metrics(row: pd.Series) -> pd.Series:
    """Calculates relative metrics from aggregated counter columns."""
    # Define all potential metrics
    print(row)
    metric_names = [
        'L1d_Load_Miss_Rate', 'L1d_Store_Miss_Rate', 'L1d_Prefetch_Miss_Rate',
        'L1i_Load_Miss_Rate',
        'LLC_Load_Miss_Rate', 'LLC_Store_Miss_Rate', 'LLC_Prefetch_Miss_Rate',
        'Branch_Load_Miss_Rate', # Or Misprediction Rate if using branch-misses
        'dTLB_Load_Miss_Rate', 'dTLB_Store_Miss_Rate',
        'iTLB_Load_Miss_Rate',
        'Node_Load_Miss_Rate', 'Node_Store_Miss_Rate', 'Node_Prefetch_Miss_Rate',
        'CPI' # Cycles Per Instruction
    ]
    metrics = pd.Series(index=metric_names, dtype=float)

    # Helper function for safe division (rate calculation)
    def safe_rate(num_event, den_event):
        num = row.get(num_event)
        den = row.get(den_event)
        # Ensure denominator exists, is not NaN, and is greater than 0
        # Ensure numerator exists and is not NaN
        if pd.notna(den) and den > 0 and pd.notna(num):
            return (num / den) * 100
        elif pd.notna(den) and den == 0 and pd.notna(num) and num == 0:
             return 0.0 # If both are zero, rate is 0%
        else:
            # Return NaN if calculation is not possible
            # (missing counter, NaN counter, or zero denominator with non-zero numerator)
            return math.nan

    # Helper function for safe division (ratio calculation, e.g., CPI)
    def safe_ratio(num_event, den_event):
        num = row.get(num_event)
        den = row.get(den_event)
        if pd.notna(den) and den > 0 and pd.notna(num):
            return num / den
        else:
            return math.nan

    # Calculate each metric
    metrics['L1d_Load_Miss_Rate'] = safe_rate('L1-dcache-load-misses', 'L1-dcache-loads')
    metrics['L1d_Store_Miss_Rate'] = safe_rate('L1-dcache-store-misses', 'L1-dcache-stores')
    metrics['L1d_Prefetch_Miss_Rate'] = safe_rate('L1-dcache-prefetch-misses', 'L1-dcache-prefetches')
    metrics['L1i_Load_Miss_Rate'] = safe_rate('L1-icache-load-misses', 'L1-icache-loads')
    metrics['LLC_Load_Miss_Rate'] = safe_rate('LLC-load-misses', 'LLC-loads')
    metrics['LLC_Store_Miss_Rate'] = safe_rate('LLC-store-misses', 'LLC-stores')
    metrics['LLC_Prefetch_Miss_Rate'] = safe_rate('LLC-prefetch-misses', 'LLC-prefetches')
    metrics['Branch_Load_Miss_Rate'] = safe_rate('branch-load-misses', 'branch-loads')
    metrics['dTLB_Load_Miss_Rate'] = safe_rate('dTLB-load-misses', 'dTLB-loads')
    metrics['dTLB_Store_Miss_Rate'] = safe_rate('dTLB-store-misses', 'dTLB-stores')
    metrics['iTLB_Load_Miss_Rate'] = safe_rate('iTLB-load-misses', 'iTLB-loads')
    metrics['Node_Load_Miss_Rate'] = safe_rate('node-load-misses', 'node-loads')
    metrics['Node_Store_Miss_Rate'] = safe_rate('node-store-misses', 'node-stores')
    metrics['Node_Prefetch_Miss_Rate'] = safe_rate('node-prefetch-misses', 'node-prefetches')
    metrics['CPI'] = safe_ratio('cycles', 'instructions')

    return metrics

def plot_time_comparison(df_times: pd.DataFrame, output_file: Path):
    """Generates a bar plot comparing baseline and perf run times."""
    print(f"--- Generating Time Comparison Plot: {output_file} ---")
    if df_times.empty:
        print("Warning: No time data available for plotting.", file=sys.stderr)
        return

    try:
        df_plot = df_times.pivot_table(index='full_id', columns='type', values='time_seconds')
        perf_cols = [col for col in df_plot.columns if col.startswith('perf_grp')]
        if not perf_cols:
             print("Warning: No perf_grp time columns found for plotting.", file=sys.stderr)
             return
        # Calculate mean only if there are valid perf times for a row
        df_plot['perf_avg'] = df_plot[perf_cols].mean(axis=1, skipna=True)

        if 'baseline' not in df_plot.columns:
            print("Warning: Baseline times missing, cannot plot comparison.", file=sys.stderr)
            # Still try to plot if perf_avg exists
            plot_cols = ['perf_avg']
            legend_labels = ["Perf Avg (across groups)"]
            colors = ['salmon']
            title = "Average Perf Run Execution Time"
        else:
            plot_cols = ['baseline', 'perf_avg']
            legend_labels = ["Baseline", "Perf Avg (across groups)"]
            colors = ['skyblue', 'salmon']
            title = "Execution Time: Baseline vs. Average Perf Run"


        df_plot_final = df_plot[plot_cols].dropna(how='all') # Plot if at least one value exists
        if df_plot_final.empty:
            print("Warning: No baseline or perf_avg data available for plotting.", file=sys.stderr)
            return

        plt.rcParams['figure.dpi'] = 100
        fig, ax = plt.subplots(figsize=(12, 7))
        fig.set_facecolor('white')
        df_plot_final.plot(
            kind="bar", ax=ax, color=colors, rot=45, width=0.8
        )
        ax.set_title(title)
        ax.set_xlabel("Benchmark and Identifier/Scale")
        ax.set_ylabel("Execution Time (seconds)")
        ax.grid(axis="y", linestyle="--", alpha=0.7, color='grey')
        ax.legend(legend_labels)
        plt.tight_layout()

        plt.savefig(output_file, format='png', dpi=150, facecolor=fig.get_facecolor(), bbox_inches='tight')
        print(f"Time plot saved successfully to {output_file}")

    except Exception as e:
        print(f"ERROR: Failed to generate or save time plot: {e}", file=sys.stderr)
    finally:
        plt.close('all') # Close all figures


def plot_relative_metrics(df_metrics: pd.DataFrame, output_file: Path):
    """Generates bar plots for ALL available relative metrics."""
    print(f"--- Generating Relative Metrics Plot (All Metrics): {output_file} ---")
    if df_metrics.empty:
        print("Warning: No relative metrics data available for plotting.", file=sys.stderr)
        return

    try:
        # Use all columns that have *any* valid data
        df_metrics_plot = df_metrics.dropna(axis=1, how='all').copy() # Work on a copy

        # Convert potential percentage columns to numeric, coercing errors
        for col in df_metrics_plot.columns:
             if 'Rate' in col: # Assume columns with 'Rate' should be percentages
                 df_metrics_plot[col] = pd.to_numeric(df_metrics_plot[col], errors='coerce')

        # Drop columns that became all NaN after coercion (if any)
        df_metrics_plot.dropna(axis=1, how='all', inplace=True)

        if df_metrics_plot.empty:
            print("Warning: No valid numeric relative metrics calculated for plotting.", file=sys.stderr)
            return

        num_metrics = len(df_metrics_plot.columns)
        if num_metrics == 0:
            print("Warning: No plottable metrics found after dropping full NaN columns.", file=sys.stderr)
            return

        print(f"Plotting the following {num_metrics} metrics: {', '.join(df_metrics_plot.columns)}")

        plt.rcParams['figure.dpi'] = 100
        fig_height = max(5, 2.5 * num_metrics)
        fig_width = 10
        fig, axes = plt.subplots(nrows=num_metrics, ncols=1, figsize=(fig_width, fig_height), sharex=True)

        if num_metrics == 1:
            axes = [axes]

        fig.set_facecolor('white')
        fig.suptitle("Relative Performance Metrics Comparison", fontsize=16, y=1.0)

        num_benchmarks = len(df_metrics_plot.index)
        colors = plt.cm.viridis(np.linspace(0, 1, num_benchmarks))

        for i, metric in enumerate(df_metrics_plot.columns):
            ax = axes[i]
            is_rate = 'Rate' in metric # Check if it's a rate for y-label

            df_metrics_plot[metric].plot(kind='bar', ax=ax, color=colors, rot=0)
            ax.set_title(metric.replace('_', ' '))
            ax.set_ylabel("Rate (%)" if is_rate else "Value") # Adjust label
            ax.grid(axis="y", linestyle="--", alpha=0.7, color='grey')

            if ax.containers:
                container = ax.containers[0]
                labels = [f'{val:.2f}' if pd.notna(val) else '' for val in container.datavalues]
                ax.bar_label(container, labels=labels, padding=3, fontsize=9, label_type='edge')
            else:
                 print(f"Warning: No bar containers found on axes for metric '{metric}' to apply labels.", file=sys.stderr)

        axes[-1].set_xlabel("Benchmark and Identifier/Scale")
        plt.xticks(rotation=45, ha='right')

        plt.tight_layout(rect=[0, 0.03, 1, 0.98])

        plt.savefig(output_file, format='png', dpi=150, facecolor=fig.get_facecolor(), bbox_inches='tight')
        print(f"Relative metrics plot saved successfully to {output_file}")

    except Exception as e:
        print(f"ERROR: Failed to generate or save relative metrics plot: {e}", file=sys.stderr)
    finally:
        plt.close('all') # Close all figures


def create_markdown_image_link(image_path: Path, report_dir: Path) -> str:
    """Returns a Markdown string to link to an image file using its path."""
    # Renamed from embed_image_markdown to reflect functionality
    if not image_path.exists():
        print(f"Warning: Image file not found for link: {image_path}", file=sys.stderr)
        return f"*[Image not found: {image_path.name}]*"
    try:
        relative_path = image_path.relative_to(report_dir)
        # Convert potential Windows paths to forward slashes for Markdown compatibility
        link_path = str(relative_path).replace('\\', '/')
        return f"![{image_path.stem}]({link_path})"
    except ValueError:
        print(f"Warning: Could not create relative path for {image_path}. Using filename only.", file=sys.stderr)
        link_path = image_path.name
        return f"![{image_path.stem}]({link_path})"
    except Exception as e:
        print(f"Error creating image link for {image_path}: {e}", file=sys.stderr)
        return f"*[Error linking image: {image_path.name}]*"

# --- Main Execution ---

if __name__ == "__main__":
    print(f"--- Analyzing Perf results ---")
    print(f"Slurm logs directory: {SLURM_LOGS_DIR}")
    print(f"Perf outputs directory: {PERF_OUTPUTS_DIR}")
    print(f"Report output directory: {REPORT_OUTPUT_DIR}")

    if not SLURM_LOGS_DIR.is_dir():
        print(f"ERROR: Slurm logs directory not found: {SLURM_LOGS_DIR}", file=sys.stderr)
        sys.exit(1)
    if not PERF_OUTPUTS_DIR.is_dir():
        print(f"ERROR: Perf outputs directory not found: {PERF_OUTPUTS_DIR}", file=sys.stderr)
        sys.exit(1)

    # --- 1. Parse Slurm Logs for Execution Times ---
    time_results = []
    print("\n--- Parsing Slurm Logs for Execution Times ---")
    log_files = list(SLURM_LOGS_DIR.glob("*.log"))
    print(f"Found {len(log_files)} files in {SLURM_LOGS_DIR}")
    for log_file in log_files:
        match = SLURM_FILENAME_REGEX.match(log_file.name)
        if not match:
            # print(f"DEBUG: Skipping file (no regex match): {log_file.name}")
            continue
        benchmark, identifier, run_type_full = match.group(1), match.group(2), match.group(3)
        full_id = f"{benchmark}_{identifier}"
        real_time = extract_time_from_log(log_file)
        if real_time is not None:
            # print(f"DEBUG: Found time for {full_id} ({run_type_full}): {real_time:.2f}s")
            time_results.append({
                "full_id": full_id, "type": run_type_full, "time_seconds": real_time,
            })
        else:
             print(f"Warning: Could not extract time from {log_file.name}", file=sys.stderr)

    if not time_results:
        print("WARNING: No execution times could be extracted from Slurm logs.", file=sys.stderr)
        # Don't exit, maybe perf data is still useful
        df_times = pd.DataFrame(columns=["full_id", "type", "time_seconds"]) # Create empty df
    else:
        df_times = pd.DataFrame(time_results)
        print(f"Successfully parsed time results for {len(df_times)} runs.")

    # --- 2. Parse Perf Output Files for Counters ---
    perf_results = []
    all_found_counters = set()
    print("\n--- Parsing Perf Output Files for Counters ---")
    perf_files = list(PERF_OUTPUTS_DIR.glob("perf.out.*"))
    print(f"Found {len(perf_files)} files in {PERF_OUTPUTS_DIR}")
    for perf_file in perf_files:
        match = PERF_FILENAME_REGEX.match(perf_file.name)
        if not match:
            # print(f"DEBUG: Skipping file (no regex match): {perf_file.name}")
            continue
        benchmark, identifier, group_num_str = match.group(1), match.group(2), match.group(3)
        try:
            group_num = int(group_num_str)
        except ValueError:
            print(f"Warning: Invalid group number in filename {perf_file.name}", file=sys.stderr)
            continue

        full_id = f"{benchmark}_{identifier}"
        counters = parse_perf_output(perf_file)
        if counters:
            # print(f"DEBUG: Parsed counters for {full_id} (grp {group_num}): {list(counters.keys())}")
            record = {"full_id": full_id, "group_num": group_num, **counters}
            perf_results.append(record)
            all_found_counters.update(counters.keys())
        else:
            print(f"Warning: No counters extracted from {perf_file.name}", file=sys.stderr)

    if not perf_results:
        print("ERROR: No performance counter data could be extracted from perf output files. Exiting.", file=sys.stderr)
        sys.exit(1)

    df_perf_raw = pd.DataFrame(perf_results)
    print(f"Successfully parsed perf counter results for {len(df_perf_raw)} groups.")
    print(f"Counters found across all files: {sorted(list(all_found_counters))}")

    # --- 3. Aggregate Perf Counters per Benchmark Run ---
    # Ensure all potentially expected counter columns exist before aggregation
    # Use NaN for missing counters instead of 0 to distinguish from actual zero counts
    for counter in ALL_TARGET_COUNTERS:
        if counter not in df_perf_raw.columns:
            df_perf_raw[counter] = np.nan # Use NaN for missing

    # Define counters to aggregate: intersection of desired and found counters
    counters_to_aggregate = sorted(list(all_found_counters.intersection(ALL_TARGET_COUNTERS)))
    if not counters_to_aggregate:
         print("ERROR: None of the target counters were found in the perf output files. Exiting.", file=sys.stderr)
         sys.exit(1)

    print(f"Aggregating these counters by summing across groups: {counters_to_aggregate}")
    # Group by full_id and sum. Use min_count=1 so that if all groups had NaN for a counter, the sum is NaN.
    # If at least one group had a number, NaNs are treated as 0 in the sum.
    df_perf_agg = df_perf_raw.groupby("full_id")[counters_to_aggregate].sum(min_count=1)

    print("\n--- Aggregated Performance Counters (Sum across groups) ---")
    if df_perf_agg.empty:
        print("WARNING: Aggregated performance counter DataFrame is empty.")
    else:
        # Display with nice formatting for large numbers, showing N/A for NaN
        print(df_perf_agg.to_string(max_rows=20, float_format="{:,.0f}".format))

    # --- 4. Calculate Time Overhead ---
    print("\n--- Calculating Time Overhead ---")
    if df_times.empty:
        print("WARNING: Time data is empty, cannot calculate overhead.")
        df_times_pivot = pd.DataFrame(index=df_perf_agg.index) # Use index from perf data if times are missing
        df_times_pivot['baseline'] = np.nan
    else:
        # Use pivot_table, ensure index matches df_perf_agg if possible
        df_times_pivot = df_times.pivot_table(index='full_id', columns='type', values='time_seconds')
        # Reindex to match the benchmarks found in perf data, filling missing times with NaN
        df_times_pivot = df_times_pivot.reindex(df_perf_agg.index)

    if 'baseline' not in df_times_pivot.columns:
        print("WARNING: 'baseline' time data is missing or incomplete. Overhead calculation may be partial.")
        df_times_pivot['baseline'] = np.nan # Ensure column exists

    overhead_cols = []
    perf_group_cols = sorted([c for c in df_times_pivot.columns if c.startswith('perf_grp')])

    for grp_col in perf_group_cols:
        overhead_col = f"{grp_col}_overhead_%"
        overhead_cols.append(overhead_col)
        # Calculate overhead safely, handling potential NaNs
        baseline_time = df_times_pivot['baseline']
        perf_time = df_times_pivot[grp_col]
        # Ensure baseline > 0 to avoid division by zero or meaningless results
        mask = pd.notna(baseline_time) & (baseline_time > 0) & pd.notna(perf_time)
        df_times_pivot[overhead_col] = np.where(
            mask,
            ((perf_time - baseline_time) / baseline_time) * 100,
            np.nan
        )

    # Calculate average overhead, skipping NaNs
    if overhead_cols: # Only calculate if there were perf groups
        df_times_pivot['avg_overhead_%'] = df_times_pivot[overhead_cols].mean(axis=1, skipna=True)
    else:
        df_times_pivot['avg_overhead_%'] = np.nan

    print("\n--- Time Data with Overhead Calculation ---")
    cols_to_show = ['baseline'] + perf_group_cols + ['avg_overhead_%']
    # Ensure columns exist before trying to display them
    cols_to_show = [col for col in cols_to_show if col in df_times_pivot.columns]
    if not cols_to_show:
        print("WARNING: No time or overhead columns available to display.")
    else:
        print(df_times_pivot[cols_to_show].to_string(float_format="%.2f"))


    # --- 5. Calculate Relative Metrics ---
    print("\n--- Calculating Relative Metrics ---")
    if df_perf_agg.empty:
        print("WARNING: Aggregated perf data is empty, cannot calculate relative metrics.")
        df_relative_metrics = pd.DataFrame() # Empty DataFrame
    else:
        df_relative_metrics = df_perf_agg.apply(calculate_relative_metrics, axis=1)
        print("\n--- Calculated Relative Metrics (%) ---")
        if df_relative_metrics.empty:
            print("WARNING: Relative metrics DataFrame is empty after calculation.")
        else:
            print(df_relative_metrics.to_string(float_format="%.3f")) # Increased precision

    # --- 6. Generate Plots ---
    # Pass the potentially modified df_times_pivot which is aligned with perf data index
    plot_time_comparison(df_times_pivot.reset_index().melt(id_vars='full_id', var_name='type', value_name='time_seconds'), OUTPUT_TIME_PLOT_FILE)
    plot_relative_metrics(df_relative_metrics, OUTPUT_REL_METRICS_PLOT_FILE)

    # --- 7. Generate Markdown Report ---
    print(f"\n--- Generating Markdown Report: {OUTPUT_MARKDOWN_FILE} ---")
    md_io = io.StringIO()
    md_io.write("# Performance Analysis Report\n\n")
    md_io.write(f"*   **Slurm Logs:** `{SLURM_LOGS_DIR}`\n")
    md_io.write(f"*   **Perf Outputs:** `{PERF_OUTPUTS_DIR}`\n")
    md_io.write(f"*   **Report Generated:** `{pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}`\n\n")

    # --- Time and Overhead Table ---
    md_io.write("## Execution Time and Perf Overhead\n\n")
    md_io.write("Compares baseline execution time with the time taken for each `perf stat` group run. Overhead is relative to the baseline.\n\n")
    # Use the same columns as printed to console
    if not cols_to_show:
         md_io.write("*No time or overhead data available to display.*\n\n")
    else:
        df_time_table = df_times_pivot[cols_to_show].copy()
        # Improve column names for Markdown
        df_time_table.rename(columns={'baseline': 'Baseline Time (s)'}, inplace=True)
        for col in perf_group_cols:
            df_time_table.rename(columns={col: f"Perf Grp {col.split('grp')[-1]} Time (s)"}, inplace=True)
        df_time_table.rename(columns={'avg_overhead_%': 'Avg. Overhead (%)'}, inplace=True)
        print("DEBUG: Attempting to write Time/Overhead table to Markdown.")
        try:
            md_io.write(df_time_table.to_markdown(floatfmt=".2f"))
            md_io.write("\n\n")
            print("DEBUG: Time/Overhead table written to Markdown buffer.")
        except Exception as e:
            print(f"ERROR: Failed to generate Time/Overhead Markdown table: {e}", file=sys.stderr)
            md_io.write(f"*Error generating time table: {e}*\n\n")

    # --- Time Plot ---
    md_io.write("### Time Comparison Plot\n\n")
    md_io.write(create_markdown_image_link(OUTPUT_TIME_PLOT_FILE, REPORT_OUTPUT_DIR))
    md_io.write("\n\n")

    # --- Raw Aggregated Counters Table ---
    md_io.write("## Aggregated Performance Counters (Raw Values)\n\n")
    md_io.write("Total counts for each hardware event, summed across all `perf stat` groups for a given benchmark run. Values are raw counts (N/A indicates the counter was missing, unsupported, or NaN in all groups).\n\n")
    print(f"DEBUG: Attempting to write df_perf_agg to Markdown. Shape: {df_perf_agg.shape}")
    if df_perf_agg.empty:
        print("WARNING: df_perf_agg is empty, skipping Markdown table.", file=sys.stderr)
        md_io.write("*Aggregated performance counters table skipped because data frame was empty.*\n\n")
    else:
        try:
            # Use integer format with commas for readability, handle NaN
            md_io.write(df_perf_agg.to_markdown())
            md_io.write("\n\n")
            print("DEBUG: Aggregated counters table written to Markdown buffer.")
        except Exception as e:
            print(f"ERROR: Failed to generate Aggregated Counters Markdown table: {e}", file=sys.stderr)
            md_io.write(f"*Error generating raw counters table: {e}*\n\n")

    # --- Relative Metrics Table ---
    md_io.write("## Relative Performance Metrics\n\n")
    md_io.write("Key relative metrics calculated from the aggregated counters (N/A indicates the metric could not be calculated, e.g., due to missing counters or division by zero).\n\n")
    print(f"DEBUG: Attempting to write df_relative_metrics to Markdown. Shape: {df_relative_metrics.shape}")
    if df_relative_metrics.empty:
        print("WARNING: df_relative_metrics is empty, skipping Markdown table.", file=sys.stderr)
        md_io.write("*Relative metrics table skipped because data frame was empty.*\n\n")
    else:
        try:
            # Display relative metrics with more precision
            md_io.write(df_relative_metrics.to_markdown())
            md_io.write("\n\n")
            print("DEBUG: Relative metrics table written to Markdown buffer.")
        except Exception as e:
            print(f"ERROR: Failed to generate Relative Metrics Markdown table: {e}", file=sys.stderr)
            md_io.write(f"*Error generating relative metrics table: {e}*\n\n")

    # --- Relative Metrics Calculation Explanation --- <--- NEW SECTION
    md_io.write("## Explanation of Calculated Relative Metrics\n\n")
    md_io.write("The relative metrics are calculated using the aggregated raw counters as follows:\n\n")
    md_io.write("*   **L1d_Load_Miss_Rate (%)**: `(L1-dcache-load-misses / L1-dcache-loads) * 100`\n")
    md_io.write("*   **L1d_Store_Miss_Rate (%)**: `(L1-dcache-store-misses / L1-dcache-stores) * 100`\n")
    md_io.write("*   **L1d_Prefetch_Miss_Rate (%)**: `(L1-dcache-prefetch-misses / L1-dcache-prefetches) * 100`\n")
    md_io.write("*   **L1i_Load_Miss_Rate (%)**: `(L1-icache-load-misses / L1-icache-loads) * 100`\n")
    md_io.write("*   **LLC_Load_Miss_Rate (%)**: `(LLC-load-misses / LLC-loads) * 100`\n")
    md_io.write("*   **LLC_Store_Miss_Rate (%)**: `(LLC-store-misses / LLC-stores) * 100`\n")
    md_io.write("*   **LLC_Prefetch_Miss_Rate (%)**: `(LLC-prefetch-misses / LLC-prefetches) * 100`\n")
    md_io.write("*   **Branch_Load_Miss_Rate (%)**: `(branch-load-misses / branch-loads) * 100` (Note: This might represent branch *misses* if `branch-misses` event was used instead of `branch-load-misses`)\n")
    md_io.write("*   **dTLB_Load_Miss_Rate (%)**: `(dTLB-load-misses / dTLB-loads) * 100`\n")
    md_io.write("*   **dTLB_Store_Miss_Rate (%)**: `(dTLB-store-misses / dTLB-stores) * 100`\n")
    md_io.write("*   **iTLB_Load_Miss_Rate (%)**: `(iTLB-load-misses / iTLB-loads) * 100`\n")
    md_io.write("*   **Node_Load_Miss_Rate (%)**: `(node-load-misses / node-loads) * 100` (Often relates to NUMA remote memory accesses)\n")
    md_io.write("*   **Node_Store_Miss_Rate (%)**: `(node-store-misses / node-stores) * 100` (Often relates to NUMA remote memory accesses)\n")
    md_io.write("*   **Node_Prefetch_Miss_Rate (%)**: `(node-prefetch-misses / node-prefetches) * 100` (Often relates to NUMA remote memory accesses)\n")
    md_io.write("*   **CPI (Cycles Per Instruction)**: `cycles / instructions` (Lower is generally better)\n\n")
    print("DEBUG: Explanation section written to Markdown buffer.")

    # --- Relative Metrics Plot ---
    md_io.write("### Relative Metrics Comparison Plot\n\n")
    md_io.write("Visual comparison of the calculated relative metrics.\n\n")
    md_io.write(create_markdown_image_link(OUTPUT_REL_METRICS_PLOT_FILE, REPORT_OUTPUT_DIR))
    md_io.write("\n\n")

    # --- Save Markdown File ---
    print(f"DEBUG: Final Markdown content length before writing: {len(md_io.getvalue())}")
    try:
        with open(OUTPUT_MARKDOWN_FILE, "w", encoding='utf-8') as f: # Specify encoding
            f.write(md_io.getvalue())
        print(f"Markdown report saved successfully to {OUTPUT_MARKDOWN_FILE}")
    except Exception as e:
        print(f"ERROR: Failed to save Markdown report to {OUTPUT_MARKDOWN_FILE}: {e}", file=sys.stderr)
        # Also print the report content to stderr for inspection if saving fails
        print("\n--- START OF FAILED MARKDOWN CONTENT ---", file=sys.stderr)
        print(md_io.getvalue(), file=sys.stderr)
        print("--- END OF FAILED MARKDOWN CONTENT ---", file=sys.stderr)


    md_io.close()
    print("\n--- Analysis Complete ---")

