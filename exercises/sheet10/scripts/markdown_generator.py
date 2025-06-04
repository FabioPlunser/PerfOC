#!/usr/bin/env python3

import pandas as pd
import numpy as np
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class MarkdownGenerator:
    def __init__(self, tables_dir):
        self.tables_dir = Path(tables_dir)

    def generate_summary_statistics(self, df):
        """Generate summary statistics table."""
        success_df = df[~df.get("error", True)].copy()

        if success_df.empty:
            return ""

        # Overall summary
        summary_stats = {
            "Metric": ["Total Runs", "Successful Runs", "Failed Runs", "Success Rate"],
            "Value": [
                len(df),
                len(success_df),
                len(df) - len(success_df),
                f"{len(success_df) / len(df) * 100:.1f}%",
            ],
        }

        summary_table = pd.DataFrame(summary_stats).to_markdown(index=False)

        return f"""## Summary Statistics

{summary_table}

"""

    def generate_performance_rankings(self, df):
        """Generate performance rankings table."""
        success_df = df[~df.get("error", True)].copy()

        if success_df.empty or "ops_per_second" not in success_df.columns:
            return ""

        # Calculate mean performance for each data structure
        perf_ranking = (
            success_df.groupby("container")
            .agg({"ops_per_second": ["mean", "std", "count"]})
            .round(2)
        )

        perf_ranking.columns = ["Mean Ops/sec", "Std Dev", "Count"]
        perf_ranking = perf_ranking.sort_values("Mean Ops/sec", ascending=False)
        perf_ranking = perf_ranking.reset_index()

        # Add rank
        perf_ranking.insert(0, "Rank", range(1, len(perf_ranking) + 1))

        return f"""## Performance Rankings (Overall)

{perf_ranking.to_markdown(index=False)}

"""

    def generate_detailed_comparison(self, df):
        """Generate detailed comparison by configuration."""
        success_df = df[~df.get("error", True)].copy()

        if success_df.empty:
            return ""

        # Group by configuration
        detailed = (
            success_df.groupby(
                ["container", "size", "elem_size", "ratio"]
            )
            .agg(
                {
                    "ops_per_second": ["mean", "std"],
                    "peak_memory_mb": (
                        ["mean", "std"]
                        if "peak_memory_mb" in success_df.columns
                        else ["mean"]
                    ),
                }
            )
            .round(3)
        )

        # Flatten column names
        detailed.columns = [f"{col[1]}_{col[0]}" for col in detailed.columns]
        
        # Reset index with drop=False to avoid column name conflicts
        detailed = detailed.reset_index(drop=False)

        # Rename columns for clarity
        column_mapping = {
            "mean_ops_per_second": "Avg Ops/sec",
            "std_ops_per_second": "Ops/sec StdDev",
            "mean_peak_memory_mb": "Avg Memory (MB)",
            "std_peak_memory_mb": "Memory StdDev (MB)",
        }
        detailed = detailed.rename(columns=column_mapping)

        return f"""## Detailed Performance by Configuration

{detailed.to_markdown(index=False)}

"""

    def generate_chunk_size_analysis(self, df):
        """Generate chunk size analysis for unrolled and tiered structures."""
        success_df = df[~df.get("error", True)].copy()

        sections = []

        # Unrolled linked lists
        unrolled_data = success_df[
            success_df["container"].str.startswith("unrolled")
        ]
        if not unrolled_data.empty:
            unrolled_data = unrolled_data.copy()
            unrolled_data["chunk_size"] = (
                unrolled_data["container"]
                .str.extract(r"unrolled_linkedlist_(\d+)")
                .astype(int)
            )

            chunk_analysis = (
                unrolled_data.groupby(["chunk_size", "size"])
                .agg({"ops_per_second": "mean"})
                .round(2)
                .reset_index()
            )

            pivot_unrolled = chunk_analysis.pivot(
                index="chunk_size", columns="size", values="ops_per_second"
            )

            sections.append(
                f"""### Unrolled Linked Lists - Chunk Size Performance

{pivot_unrolled.to_markdown()}

"""
            )

        # Tiered arrays
        tiered_data = success_df[success_df["container"].str.startswith("tiered")]
        if not tiered_data.empty:
            tiered_data = tiered_data.copy()
            tiered_data["chunk_size"] = (
                tiered_data["container"]
                .str.extract(r"tiered_array_(\d+)")
                .astype(int)
            )

            chunk_analysis = (
                tiered_data.groupby(["chunk_size", "size"])
                .agg({"ops_per_second": "mean"})
                .round(2)
                .reset_index()
            )

            pivot_tiered = chunk_analysis.pivot(
                index="chunk_size", columns="size", values="ops_per_second"
            )

            sections.append(
                f"""### Tiered Arrays - Chunk Size Performance

{pivot_tiered.to_markdown()}

"""
            )

        if sections:
            return f"""## Chunk Size Analysis

{''.join(sections)}"""
        else:
            return ""

    def generate_instruction_mix_impact(self, df):
        """Generate analysis of instruction mix impact."""
        success_df = df[~df.get("error", True)].copy()

        if success_df.empty:
            return ""

        # Calculate performance impact of instruction mix
        mix_impact = (
            success_df.groupby(["container", "ratio"])
            .agg({"ops_per_second": "mean"})
            .round(2)
            .reset_index()
        )

        pivot_mix = mix_impact.pivot(
            index="container", columns="ratio", values="ops_per_second"
        )

        # Calculate performance degradation
        if 0.0 in pivot_mix.columns:
            degradation = pivot_mix.copy()
            baseline = degradation[0.0]

            for col in degradation.columns:
                if col != 0.0:
                    degradation[col] = (degradation[col] / baseline * 100).round(1)

            degradation = degradation.drop(columns=[0.0])
            degradation.columns = [
                f"{col*100:.0f}% ins/del (% of read-only)"
                for col in degradation.columns
            ]

            return f"""## Instruction Mix Impact

### Performance by Instruction Mix (Ops/sec)
{pivot_mix.to_markdown()}

### Performance Relative to Read-Only (%)
{degradation.to_markdown()}

"""
        else:
            return f"""## Instruction Mix Impact

### Performance by Instruction Mix (Ops/sec)
{pivot_mix.to_markdown()}

"""

    def generate_best_worst_analysis(self, df):
        """Generate best and worst performing configurations."""
        success_df = df[~df.get("error", True)].copy()

        if success_df.empty or "ops_per_second" not in success_df.columns:
            return ""

        # Find best and worst performing configurations
        best = success_df.loc[success_df["ops_per_second"].idxmax()]
        worst = success_df.loc[success_df["ops_per_second"].idxmin()]

        best_config = f"""- **Data Structure**: {best['container']}
- **Elements**: {best['size']:,}
- **Element Size**: {best['elem_size']} bytes
- **Ins/Del Ratio**: {best['ratio']*100:.1f}%
- **Performance**: {best['ops_per_second']:,.0f} ops/sec"""

        worst_config = f"""- **Data Structure**: {worst['container']}
- **Elements**: {worst['size']:,}
- **Element Size**: {worst['elem_size']} bytes
- **Ins/Del Ratio**: {worst['ratio']*100:.1f}%
- **Performance**: {worst['ops_per_second']:,.0f} ops/sec"""

        speedup = best["ops_per_second"] / worst["ops_per_second"]

        return f"""## Best vs Worst Performance

### Best Performing Configuration
{best_config}

### Worst Performing Configuration
{worst_config}

**Performance Difference**: {speedup:.1f}x speedup

"""

    def generate_full_report(self, df):
        """Generate complete markdown report."""
        logger.info("Generating markdown report...")

        # Save raw data tables
        success_df = df[~df.get("error", True)].copy()
        success_df.to_csv(self.tables_dir / "successful_results.csv", index=False)

        # Generate report sections
        report_sections = [
            "# Data Structure Benchmark Results\n\n",
            f"**Generated on**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n",
            self.generate_summary_statistics(df),
            self.generate_performance_rankings(df),
            self.generate_best_worst_analysis(df),
            self.generate_chunk_size_analysis(df),
            self.generate_instruction_mix_impact(df),
            self.generate_detailed_comparison(df),
        ]

        # Write full report
        report_content = "".join(section for section in report_sections if section)

        with open(self.tables_dir / "benchmark_report.md", "w") as f:
            f.write(report_content)

        logger.info(
            f"Markdown report saved to {self.tables_dir / 'benchmark_report.md'}"
        )
