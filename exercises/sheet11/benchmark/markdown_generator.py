import pandas as pd
import config
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def generate_markdown_tables(df: pd.DataFrame):
    """Generates Markdown tables summarizing benchmark results."""
    if df.empty:
        logger.warning("DataFrame is empty. Skipping Markdown report generation.")
        return ""

    # Aggregate data: mean and std over repetitions
    df_summary = (
        df.groupby(["program", "n_value"])
        .agg(
            user_time_mean=("user_time_s", "mean"),
            user_time_std=("user_time_s", "std"),
            system_time_mean=("system_time_s", "mean"),
            system_time_std=("system_time_s", "std"),
            elapsed_time_mean=("elapsed_time_s", "mean"),
            elapsed_time_std=("elapsed_time_s", "std"),
            max_rss_mean_mb=("max_rss_mb", "mean"),
            max_rss_std_mb=("max_rss_mb", "std"),
            internal_time_s_precise=("internal_time_s_precise", "mean"),
            internal_time_ns=("internal_time_s_precise", "mean"),
            

            runs=("repetition", "count"),  # To show number of successful runs averaged
        )
        .reset_index()
    )

    # Format numbers for readability in Markdown
    for col in [
        "max_rss_mean_mb",
        "max_rss_std_mb",
        
    ]:
        df_summary[col] = df_summary[col].apply(
            lambda x: f"{x:.4f}" if pd.notnull(x) else "N/A"
        )

    df_summary = df_summary.sort_values(by=["program", "n_value"])

    # Pivot for a wide table comparing programs side-by-side for each N
    # This can get very wide. Let's do a long table first.

    md_content = f"# Delannoy Benchmark Report\n\n"
    md_content += f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    md_content += (
        f"Number of repetitions per (Program, N) pair: {config.NUM_REPETITIONS}\n\n"
    )

    md_content += "## Summary Table (Mean Values)\n\n"

    # Select and rename columns for the main table
    table_df = df_summary[
        [
            "program",
            "n_value",
            "max_rss_mean_mb",
            "max_rss_std_mb",
            "internal_time_s_precise",
        ]
    ].copy()
    table_df.columns = [
        "Program",
        "N",
        "Peak Memory (MB)",
        "Memory StdDev",
        "Internal Time (s)",
    ]

    md_content += table_df.to_markdown(index=False)
    md_content += "\n\n"

    # Add a section for any runs that had errors or missing data
    error_df = df[
        df["error_detected"] | df["user_time_s"].isnull() | df["max_rss_mb"].isnull()
    ]
    if not error_df.empty:
        md_content += "## Problematic Runs (Errors or Missing Data)\n\n"
        md_content += error_df[
            [
                "program",
                "n_value",
                "repetition",
                "log_file",
                "verification_status",
                "parse_error",
            ]
        ].to_markdown(index=False)
        md_content += "\n\n"

    return md_content


def save_markdown_report(results_df: pd.DataFrame):
    logger.info("Generating Markdown report...")
    report_content = generate_markdown_tables(results_df)
    with open(config.REPORT_FILE, "w") as f:
        f.write(report_content)
    logger.info(f"Markdown report saved to {config.REPORT_FILE.resolve()}")
