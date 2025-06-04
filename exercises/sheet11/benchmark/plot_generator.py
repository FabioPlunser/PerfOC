import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import config
import logging

logger = logging.getLogger(__name__)
plt.style.use(config.PLOT_STYLE)


def save_plot(fig, filename_prefix: str):
    """Saves the plot to the configured directory."""
    filepath = config.PLOTS_DIR / f"{filename_prefix}.{config.PLOT_FORMAT}"
    fig.tight_layout()
    fig.savefig(filepath, dpi=config.PLOT_DPI)
    plt.close(fig)
    logger.info(f"Saved plot: {filepath}")


def plot_time_comparison(df: pd.DataFrame):
    """Plots User Time, System Time, and Elapsed Time vs N."""
    if df.empty:
        logger.warning("DataFrame is empty. Skipping time comparison plot.")
        return

    # Aggregate data: mean over repetitions
    # Ensure n_value is numeric for plotting
    df["n_value"] = pd.to_numeric(df["n_value"], errors="coerce")

    # Filter out rows where essential time data might be missing
    df_agg = df.dropna(subset=["user_time_s", "system_time_s", "elapsed_time_s"])
    if df_agg.empty:
        logger.warning("No valid data after dropping NaNs for time plotting.")
        return

    df_agg = (
        df_agg.groupby(["program", "n_value"])
        .agg(
            user_time_mean=("user_time_s", "mean"),
            system_time_mean=("system_time_s", "mean"),
            elapsed_time_mean=("elapsed_time_s", "mean"),
            user_time_std=("user_time_s", "std"),
            system_time_std=("system_time_s", "std"),
            elapsed_time_std=("elapsed_time_s", "std"),
        )
        .reset_index()
    )

    time_metrics = {
        "user_time": ("User Time (s)", "user_time_mean", "user_time_std"),
        "system_time": ("System Time (s)", "system_time_mean", "system_time_std"),
        "elapsed_time": (
            "Elapsed Wall Clock Time (s)",
            "elapsed_time_mean",
            "elapsed_time_std",
        ),
    }

    for metric_key, (title, mean_col, std_col) in time_metrics.items():
        fig, ax = plt.subplots(figsize=(12, 7))
        # Use line plot for time progression with N
        sns.lineplot(
            data=df_agg,
            x="n_value",
            y=mean_col,
            hue="program",
            style="program",
            markers=True,
            dashes=False,
            ax=ax,
            linewidth=2,
        )
        # Optional: Add error bars if std is meaningful and data sufficient
        # for i, program in enumerate(df_agg['program'].unique()):
        #     prog_data = df_agg[df_agg['program'] == program]
        #     ax.errorbar(prog_data['n_value'], prog_data[mean_col], yerr=prog_data[std_col], fmt='none', capsize=5, label=f'_{program} std')

        ax.set_title(f"{title} vs. N (Log Scale Y-axis)")
        ax.set_xlabel("N Value")
        ax.set_ylabel(title + " (Log Scale)")
        ax.set_yscale("log")  # Time often grows exponentially or polynomially
        ax.legend(title="Program")
        ax.grid(True, which="both", ls="--", alpha=0.7)
        save_plot(fig, f"delannoy_{metric_key}_vs_n")


def plot_memory_comparison(df: pd.DataFrame):
    """Plots Maximum Resident Set Size (MB) vs N."""
    if df.empty or "max_rss_mb" not in df.columns:
        logger.warning(
            "DataFrame is empty or 'max_rss_mb' is missing. Skipping memory plot."
        )
        return

    df["n_value"] = pd.to_numeric(df["n_value"], errors="coerce")
    df_agg = df.dropna(subset=["max_rss_mb"])
    if df_agg.empty:
        logger.warning("No valid data after dropping NaNs for memory plotting.")
        return

    df_agg = (
        df_agg.groupby(["program", "n_value"])
        .agg(max_rss_mean=("max_rss_mb", "mean"), max_rss_std=("max_rss_mb", "std"))
        .reset_index()
    )

    fig, ax = plt.subplots(figsize=(12, 7))
    sns.lineplot(
        data=df_agg,
        x="n_value",
        y="max_rss_mean",
        hue="program",
        style="program",
        markers=True,
        dashes=False,
        ax=ax,
        linewidth=2,
    )
    # Optional: Error bars for memory
    # for i, program in enumerate(df_agg['program'].unique()):
    #     prog_data = df_agg[df_agg['program'] == program]
    #     ax.errorbar(prog_data['n_value'], prog_data['max_rss_mean'], yerr=prog_data['max_rss_std'], fmt='none', capsize=5, label=f'_{program} std')

    ax.set_title("Peak Memory Usage (MB) vs. N")
    ax.set_xlabel("N Value")
    ax.set_ylabel("Peak Memory (MB)")
    # Y-scale for memory might be linear or log depending on growth
    # ax.set_yscale("log") # If memory growth is exponential for some cases
    ax.legend(title="Program")
    ax.grid(True, which="both", ls="--", alpha=0.7)
    save_plot(fig, "delannoy_memory_vs_n")


def generate_all_plots(results_df: pd.DataFrame):
    logger.info("Generating plots...")
    plot_time_comparison(results_df.copy())
    plot_memory_comparison(results_df.copy())
    logger.info(f"All plots saved to {config.PLOTS_DIR.resolve()}")
