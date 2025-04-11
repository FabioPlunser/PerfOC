# report.py
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

import config # For subdirs

def create_plots(results_df: pd.DataFrame, base_output_dir):
    """Generates bar plots for each program comparing flag configurations."""
    print("\n--- Generating Plots ---")
    if results_df is None or results_df.empty:
        print("WARNING: No analysis data available to generate plots.")
        return {}

    plots_dir = base_output_dir / config.RESULTS_SUBDIR / config.PLOTS_SUBDIR
    plots_dir.mkdir(parents=True, exist_ok=True)
    programs = results_df['Program'].unique()
    plot_paths = {} # Store { prog_name: relative_path }

    # Determine plot style based on number of flag configs
    num_flags = len(results_df['FlagsID'].unique())
    use_rotation = num_flags > 7 # Rotate labels if many flags

    for prog_name in programs:
        # Ensure sorting by original order if categorical, otherwise alphabetical
        prog_df = results_df[results_df['Program'] == prog_name].sort_values('FlagsID')

        if prog_df['MeanTime'].isnull().all():
             print(f"INFO: Skipping plot for {prog_name}: No valid time data found.")
             continue

        plt.figure(figsize=(max(10, num_flags * 0.8), 6)) # Adjust width based on flags
        bars = plt.bar(prog_df['FlagsID'].astype(str), # Use string representation for plotting
                       prog_df['MeanTime'], yerr=prog_df['StdDev'], capsize=4,
                       color='cornflowerblue', edgecolor='black')

        plt.xlabel("Flag Configuration ID")
        plt.ylabel("Mean Execution Time (seconds)")
        plt.title(f"Mean Execution Time vs. Flags for {prog_name}\n"
                  f"(Error bars = stdev of successful runs)")
        plt.grid(axis='y', linestyle='--', alpha=0.6)

        if use_rotation:
            plt.xticks(rotation=45, ha='right', fontsize=8) # Rotate labels
        else:
             plt.xticks(fontsize=9)

        # Add text labels only if few bars
        if num_flags <= 10:
            for bar in bars:
                yval = bar.get_height()
                if pd.notna(yval):
                     plt.text(bar.get_x() + bar.get_width()/2.0, yval,
                              f'{yval:.3f}', va='bottom', ha='center', fontsize=8)

        # Adjust y-limit
        min_val = (prog_df['MeanTime'] - prog_df['StdDev']).min()
        max_val = (prog_df['MeanTime'] + prog_df['StdDev']).max()
        if pd.notna(min_val) and pd.notna(max_val): plt.ylim(max(0, min_val * 0.9), max_val * 1.15)
        elif pd.notna(max_val): plt.ylim(0, max_val * 1.15)
        else: plt.ylim(0)

        plot_filename = f"{prog_name}_times_vs_flags.png"
        plot_path = plots_dir / plot_filename
        try:
            plt.savefig(plot_path, bbox_inches='tight', dpi=300)
            plt.close()
            print(f"INFO: Generated plot: {plot_path}")
            plot_paths[prog_name] = plot_path.relative_to(base_output_dir)
        except Exception as e:
            print(f"ERROR: Failed to save plot {plot_path}: {e}")
            plt.close()

    print("INFO: Plot generation finished.")
    return plot_paths


def generate_markdown_report(results_df: pd.DataFrame, plot_relative_paths: dict,
                             programs_run_names: list, flag_configs: dict,
                             base_output_dir):
    """Generates the final Markdown report."""
    print("\n--- Generating Markdown Report ---")
    report_path = base_output_dir / "benchmark_report.md"
    results_dir = base_output_dir / config.RESULTS_SUBDIR

    if results_df is None or results_df.empty:
        print("WARNING: No analysis data available to generate report.")
        # Generate minimal report
        with open(report_path, "w") as f:
             f.write("# GCC Optimization Benchmarking Report\n\n")
             f.write(f"Date Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
             f.write("## Configuration\n\n")
             f.write(f"*   **Programs Selected:** {', '.join(programs_run_names)}\n")
             f.write(f"*   **Flag Configurations Tested:** {len(flag_configs)}\n")
             f.write("\n## Results\n\n")
             f.write("No analysis data was generated or available.\n")
        print(f"INFO: Generated minimal report (no data): {report_path}")
        return

    # --- Generate Full Report ---
    summary_table = results_df.pivot(index='Program', columns='FlagsID', values='MeanTime')
    program_names_analyzed = summary_table.index.tolist()

    with open(report_path, "w") as f:
        f.write("# GCC Optimization Benchmarking Report\n\n")
        f.write(f"Date Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        f.write("## Configuration\n\n")
        f.write(f"*   **GCC Version:** Module `{config.MODULES_TO_LOAD[0]}` (or similar)\n")
        f.write(f"*   **Programs Run:** {', '.join(programs_run_names)}\n")
        f.write(f"*   **Programs Analyzed:** {', '.join(program_names_analyzed)}\n")
        f.write(f"*   **Number of Runs Attempted per Configuration:** {config.DEFAULT_NUM_RUNS}\n") # Assumes constant
        f.write(f"*   **Flag Configurations Tested ({len(flag_configs)}):**\n")
        # List flag configurations used
        for flags_id, flags_list in flag_configs.items():
             f.write(f"    *   `{flags_id}`: `{' '.join(flags_list)}`\n")
        f.write("\n")

        f.write("## Summary Table: Mean Execution Time (seconds)\n\n")
        # Transpose if too many columns for better readability
        if len(flag_configs) > 6:
             f.write(summary_table.T.to_markdown(floatfmt=".4f"))
             f.write("\n\n*(Table transposed for readability)*\n\n")
        else:
             f.write(summary_table.to_markdown(floatfmt=".4f"))
             f.write("\n\n")
        f.write("*Note: Table shows mean time of successful runs. NaN indicates no successful runs were recorded/analyzed.*\n\n")

        f.write("## Performance Plots\n\n")
        f.write("Plots show mean execution time (successful runs) vs. flag configuration ID. Error bars = standard deviation.\n\n")

        for prog_name in program_names_analyzed:
            f.write(f"### {prog_name}\n\n")
            if prog_name in plot_relative_paths:
                f.write(f"![Performance Plot for {prog_name}]({plot_relative_paths[prog_name].as_posix()})\n\n") # Use posix path for md
            else:
                 f.write(f"*Plot not generated (likely no successful runs).*\n\n")

        f.write("## Discussion\n\n")
        f.write("(Add your analysis and discussion here based on the results)\n\n")
        # Add specific prompts based on the exercise mode later if needed

    print(f"INFO: Markdown report generated: {report_path}")
    print("INFO: Report generation finished.")

