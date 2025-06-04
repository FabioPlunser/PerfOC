import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import config
import logging

logger = logging.getLogger(__name__)
plt.style.use(config.PLOT_STYLE)

# Define a consistent color palette and order for the programs
program_palette = {
    "delannoy": "red",
    "delannoy_memo": "blue",
    "delannoy_tab": "green",
}
program_order = ["delannoy", "delannoy_memo", "delannoy_tab"]


def save_plot(fig, filename_prefix: str):
    """Saves the plot to the configured directory."""
    filepath = config.PLOTS_DIR / f"{filename_prefix}.{config.PLOT_FORMAT}"
    fig.tight_layout()
    fig.savefig(filepath, dpi=config.PLOT_DPI, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"Saved plot: {filepath}")


def plot_time_comparison_all_n(df_agg: pd.DataFrame):
    """
    Plots a single bar chart comparing mean elapsed time of all programs across all N values.
    N values are on the x-axis, programs are grouped by hue.
    """
    if df_agg.empty:
        logger.warning(
            "Aggregated DataFrame is empty. Skipping combined time plot."
        )
        return

    # Ensure n_value is treated as a category for distinct groups on x-axis
    # If n_value is numeric, barplot might try to treat it continuously.
    df_plot = df_agg.copy()
    df_plot["n_value_cat"] = df_plot["n_value"].astype(str)
    # Sort by numeric n_value before converting to category for correct x-axis order
    df_plot = df_plot.sort_values(by="n_value")


    fig, ax = plt.subplots(figsize=(14, 8))
    
    sns.barplot(
        x="n_value_cat", # Use categorical version for x-axis
        y="elapsed_time_mean",
        hue="program",
        data=df_plot,
        hue_order=program_order, # Ensure consistent order of programs in legend/groups
        palette=program_palette,
        ax=ax,
        dodge=True # Default, but explicit
    )

    ax.set_title("Mean Elapsed Time Comparison (All N values)")
    ax.set_xlabel("N Value")
    ax.set_ylabel("Mean Elapsed Time (seconds, Log Scale)")
    ax.set_yscale("log") # Log scale is essential for time

    ax.grid(True, which="both", ls="--", alpha=0.7, axis="y")
    ax.legend(title="Program")
    
    # Rotate x-axis labels if many N values
    if len(df_plot["n_value_cat"].unique()) > 5:
        plt.xticks(rotation=45, ha="right")

    save_plot(fig, "delannoy_elapsed_time_all_N_grouped")


def plot_memory_comparison_all_n(df_agg: pd.DataFrame):
    """
    Plots a single bar chart comparing mean peak memory of all programs across all N values.
    N values are on the x-axis, programs are grouped by hue.
    """
    if df_agg.empty:
        logger.warning(
            "Aggregated DataFrame is empty. Skipping combined memory plot."
        )
        return

    df_plot = df_agg.copy()
    df_plot["n_value_cat"] = df_plot["n_value"].astype(str)
    df_plot = df_plot.sort_values(by="n_value")

    fig, ax = plt.subplots(figsize=(14, 8))
    
    sns.barplot(
        x="n_value_cat",
        y="max_rss_mean_mb",
        hue="program",
        data=df_plot,
        hue_order=program_order,
        palette=program_palette,
        ax=ax,
        dodge=True
    )

    ax.set_title("Mean Peak Memory Usage Comparison (All N values)")
    ax.set_xlabel("N Value")
    ax.set_ylabel("Mean Peak Memory (MB)")

    ax.grid(True, which="both", ls="--", alpha=0.7, axis="y")
    ax.legend(title="Program")

    if len(df_plot["n_value_cat"].unique()) > 5:
        plt.xticks(rotation=45, ha="right")
        
    save_plot(fig, "delannoy_peak_memory_all_N_grouped")


def generate_all_plots(results_df: pd.DataFrame):
    logger.info("Generating combined bar plots for time and memory...")
    if results_df.empty:
        logger.warning("Input DataFrame is empty. No plots will be generated.")
        return

    results_df["n_value"] = pd.to_numeric(results_df["n_value"], errors="coerce")
    
    # Aggregate data: mean over repetitions
    # Time aggregation
    time_df_agg = results_df.dropna(subset=["elapsed_time_s"])
    if not time_df_agg.empty:
        time_df_agg = (
            time_df_agg.groupby(["program", "n_value"])
            .agg(elapsed_time_mean=("internal_time_s_precise", "mean"))
            .reset_index()
        )
        # Filter to only include programs we want to plot in the defined order
        time_df_agg = time_df_agg[time_df_agg['program'].isin(program_order)]
        plot_time_comparison_all_n(time_df_agg)
    else:
        logger.warning("No valid data for aggregated time plotting after dropping NaNs.")


    # Memory aggregation
    memory_df_agg = results_df.dropna(subset=["max_rss_mb"])
    if not memory_df_agg.empty:
        memory_df_agg = (
            memory_df_agg.groupby(["program", "n_value"])
            .agg(max_rss_mean_mb=("max_rss_mb", "mean"))
            .reset_index()
        )
        memory_df_agg = memory_df_agg[memory_df_agg['program'].isin(program_order)]
        plot_memory_comparison_all_n(memory_df_agg)
    else:
        logger.warning("No valid data for aggregated memory plotting after dropping NaNs.")
            
    logger.info(f"All plots saved to {config.PLOTS_DIR.resolve()}")