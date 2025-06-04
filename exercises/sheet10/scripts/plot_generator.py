#!/usr/bin/env python3

import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
import logging
from pathlib import Path
from typing import List, Optional

from config import PLOT_FORMAT, PLOT_DPI, PLOT_STYLE

logger = logging.getLogger(__name__)


class PlotGenerator:
    DATA_STRUCTURE_SORT_ORDER = [
        "array",
        "linkedlist_seq",
        "linkedlist_rand",
        "unrolled_linkedlist_8",
        "unrolled_linkedlist_16",
        "unrolled_linkedlist_32",
        "unrolled_linkedlist_64",
        "unrolled_linkedlist_128",
        "unrolled_linkedlist_256",
        "tiered_array_8",
        "tiered_array_16",
        "tiered_array_32",
        "tiered_array_64",
        "tiered_array_128",
        "tiered_array_256",
    ]

    def __init__(self, plots_dir: Path):
        self.plots_dir = Path(plots_dir)
        self.plots_dir.mkdir(parents=True, exist_ok=True)
        plt.style.use(PLOT_STYLE)

        self.palette = sns.color_palette("tab20", 20)

        self.ds_color_map = {
            ds: self.palette[i % len(self.palette)]
            for i, ds in enumerate(self.DATA_STRUCTURE_SORT_ORDER)
        }
        self.default_color_for_pandas = self.palette[
            len(self.DATA_STRUCTURE_SORT_ORDER) % len(self.palette)
        ]

    def save_plot(self, filename: str, fig=None):
        """Save plot with configured format and DPI."""
        filepath = self.plots_dir / f"{filename}.{PLOT_FORMAT}"
        if fig is None:
            fig = plt.gcf()

        fig.tight_layout()
        fig.savefig(filepath, format=PLOT_FORMAT, dpi=PLOT_DPI, bbox_inches="tight")
        plt.close(fig)
        logger.info(f"Saved plot: {filepath}")

    def _get_plot_order(self, present_structures: List[str]) -> List[str]:
        """
        Returns a sorted list of structures for plotting,
        based on DATA_STRUCTURE_SORT_ORDER.
        Structures not in DATA_STRUCTURE_SORT_ORDER are appended at the end,
        sorted alphabetically among themselves.
        """
        ordered_list = [
            s for s in self.DATA_STRUCTURE_SORT_ORDER if s in present_structures
        ]

        unknown_structures = sorted(
            [s for s in present_structures if s not in ordered_list]
        )
        ordered_list.extend(unknown_structures)
        return ordered_list

    def _get_success_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """Filters for successful runs and ensures correct column names."""
        rename_map = {
            "container": "data_structure",
            "size": "num_elements",  # "size of elements"
            "elem_size": "element_size",  # "sizeofelement"
            "ratio": "ins_del_ratio",
        }
        current_columns = df.columns.tolist()
        actual_renames = {k: v for k, v in rename_map.items() if k in current_columns}

        df_renamed = df.rename(columns=actual_renames) if actual_renames else df.copy()

        required_cols = [
            "data_structure",
            "num_elements",
            "ops_per_second",
            "element_size",
        ]
        missing_req_cols = [
            col for col in required_cols if col not in df_renamed.columns
        ]
        if missing_req_cols:
            logger.error(
                f"Missing required columns for plotting: {missing_req_cols}. "
                f"DataFrame columns: {df_renamed.columns.tolist()}."
            )
            return pd.DataFrame()

        success_df = df_renamed[
            df_renamed["ops_per_second"].notna()
            & ~df_renamed.get("error", pd.Series(False, index=df_renamed.index))
        ].copy()

        for col in [
            "num_elements",
            "element_size",
            "ins_del_ratio",
            "ops_per_second",
            "peak_memory_mb",
        ]:
            if col in success_df.columns:
                success_df[col] = pd.to_numeric(success_df[col], errors="coerce")

        #if "random_access" exists, coerce to int else default to 0
        if "random_access" in success_df.columns:
            success_df["random_access"] = pd.to_numeric(success_df["random_access"], errors="coerce").fillna(0).astype(int)
        else:
            success_df["random_access"] = 0

        return success_df.dropna(subset=["ops_per_second", "element_size"])

    def create_performance_comparison_unified_bars(self, df: pd.DataFrame):
        success_df = self._get_success_df(df)
        if success_df.empty:
            logger.warning("No data for unified performance comparison bars.")
            return

        success_df["structure_access"] = success_df["data_structure"] + success_df["random_access"].map({0: " (seq)", 1: " (rand)"})
        
        agg_df = (
            success_df.groupby(["structure_access", "num_elements"])["ops_per_second"]
            .mean()
            .reset_index()
        )
        if agg_df.empty:
            logger.warning("Aggregated data empty for unified performance bars.")
            return

        unique_num_elements = sorted(agg_df["num_elements"].unique())
        plot_hue_order = self._get_plot_order(agg_df["structure_access"].unique())

        fig, ax = plt.subplots(figsize=(18, 10))
        sns.barplot(
            x="num_elements",
            y="ops_per_second",
            hue="structure_access",
            data=agg_df,
            order=unique_num_elements,
            hue_order=plot_hue_order,
            palette=self.palette,
            ax=ax,
            estimator=np.mean,
            errorbar=None,
        )
        ax.set_title("Performance Comparison Across Data Structures", fontsize=16)
        ax.set_xlabel("Number of Elements", fontsize=14)
        ax.set_ylabel("Mean Operations per Second (Log Scale)", fontsize=14)
        ax.set_yscale("log")
        ax.tick_params(axis="x", rotation=45)
        ax.grid(True, which="both", ls="-", alpha=0.7)
        ax.legend(  # Legend title is "Data Structure" by default from hue name
            bbox_to_anchor=(1.02, 1),
            loc="upper left",
            borderaxespad=0.0,
        )
        self.save_plot("performance_comparison_unified_bars", fig=fig)

    def create_performance_relative_to_baseline_array(self, df: pd.DataFrame):
        success_df = self._get_success_df(df)
        if success_df.empty:
            logger.warning("No data for baseline comparison.")
            return

        # Construct combined label and a flag for baseline comparison
        success_df["structure_access"] = success_df["data_structure"] + success_df["random_access"].map({0: " (seq)", 1: " (rand)"})
        success_df["is_array"] = success_df["data_structure"] == "array"

        # Group on structure_access
        perf_agg = (
            success_df.groupby(["structure_access", "num_elements", "is_array"])["ops_per_second"]
            .mean()
            .reset_index()
        )

        # Baseline: only the array rows
        array_perf = perf_agg[perf_agg["is_array"]].copy()
        if array_perf.empty:
            logger.warning("No 'array' data for baseline. Skipping plot.")
            return

        # Drop is_array for cleaner merge
        array_perf = array_perf.rename(
            columns={"ops_per_second": "array_ops_per_second"}
        ).drop(columns=["is_array", "structure_access"])

        # Comparison: everything else
        comparison_df = perf_agg[~perf_agg["is_array"]].copy()
        comparison_df = pd.merge(
            comparison_df, array_perf, on=["num_elements"], how="left"
        )
        comparison_df.dropna(subset=["array_ops_per_second"], inplace=True)
        if comparison_df.empty:
            logger.warning("No data to compare against 'array' baseline.")
            return

        comparison_df["speedup_vs_array"] = (
            comparison_df["ops_per_second"] / comparison_df["array_ops_per_second"]
        )

        plot_hue_order = sorted(comparison_df["structure_access"].unique())

        fig, ax = plt.subplots(figsize=(14, 8))
        sns.barplot(
            x="num_elements",
            y="speedup_vs_array",
            hue="structure_access",
            data=comparison_df,
            palette=self.palette,
            ax=ax,
            hue_order=plot_hue_order,
        )
        ax.set_title("Performance Relative to 'array' (Speedup)", fontsize=16)
        ax.set_xlabel("Number of Elements", fontsize=14)
        ax.set_ylabel("Speedup vs. 'array' (Higher is Better)", fontsize=14)
        ax.axhline(1.0, color="red", linestyle="--", label="Baseline ('array')")
        ax.tick_params(axis="x", rotation=45)
        ax.legend(
            bbox_to_anchor=(1.02, 1), loc="upper left"
        )
        ax.grid(True, axis="y", linestyle="--", alpha=0.7)
        self.save_plot("performance_vs_baseline_array", fig=fig)
    

    def create_performance_heatmap(
        self,
        df: pd.DataFrame,
        element_size_filter: Optional[int] = 512,  # This is sizeofelement
        ins_del_ratio_filter: Optional[float] = 0.01,
    ):
        success_df = self._get_success_df(df)
        if success_df.empty:
            logger.warning("No data for performance heatmap.")
            return
        
        success_df["structure_access"] = success_df["data_structure"] + success_df["random_access"].map({0: " (seq)", 1: " (rand)"})
        
        filtered_df = success_df
        title_suffix_parts = []

        if element_size_filter is not None and "element_size" in filtered_df.columns:
            if element_size_filter in filtered_df["element_size"].unique():
                filtered_df = filtered_df[
                    filtered_df["element_size"] == element_size_filter
                ]
                title_suffix_parts.append(f"Element Size: {element_size_filter}B")
            else:
                logger.warning(
                    f"Element size {element_size_filter}B not found for heatmap. Averaging over element sizes."
                )
                title_suffix_parts.append("Avg Element Size")
        elif element_size_filter is None:  # Explicitly requested to average
            title_suffix_parts.append("Avg Element Size")

        if ins_del_ratio_filter is not None and "ins_del_ratio" in filtered_df.columns:
            if any(
                np.isclose(filtered_df["ins_del_ratio"].unique(), ins_del_ratio_filter)
            ):
                filtered_df = filtered_df[
                    np.isclose(filtered_df["ins_del_ratio"], ins_del_ratio_filter)
                ]
                title_suffix_parts.append(f"Ins/Del: {ins_del_ratio_filter*100:.0f}%")
            else:
                logger.warning(
                    f"Ins/Del ratio {ins_del_ratio_filter} not found for heatmap. Averaging over ratios."
                )
                title_suffix_parts.append("Avg Ins/Del Ratio")

        title_suffix = (
            " (" + ", ".join(title_suffix_parts) + ")" if title_suffix_parts else ""
        )

        if filtered_df.empty:
            logger.warning(
                f"No data after filtering for heatmap{title_suffix}. Skipping."
            )
            return

        heatmap_data = (
            filtered_df.groupby(["structure_access", "num_elements"])["ops_per_second"]
            .mean()
            .unstack()
            .fillna(0)
        )
        if heatmap_data.empty:
            logger.warning(f"Pivoted heatmap data empty{title_suffix}. Skipping.")
            return

        sorted_index = self._get_plot_order(heatmap_data.index.tolist())
        if sorted_index and list(heatmap_data.index) != sorted_index:
            heatmap_data = heatmap_data.reindex(sorted_index)

        plt.figure(figsize=(16, max(8, len(heatmap_data.index) * 0.6)))
        sns.heatmap(
            heatmap_data,
            annot=True,
            fmt=".1e",
            cmap="viridis",
            linewidths=0.5,
            cbar_kws={"label": "Mean Operations per Second"},
        )
        plt.title(f"Performance Heatmap{title_suffix}", fontsize=16)
        plt.xlabel("Number of Elements", fontsize=14)
        plt.ylabel("Data Structure + access type", fontsize=14)
        plt.xticks(rotation=45, ha="right")
        plt.yticks(rotation=0)

        # Sanitize filename from filters
        elem_size_fn = (
            str(element_size_filter) if element_size_filter is not None else "all"
        )
        ratio_fn = (
            str(ins_del_ratio_filter).replace(".", "_")
            if ins_del_ratio_filter is not None
            else "all"
        )
        self.save_plot(f"performance_heatmap_elemsize{elem_size_fn}_ratio{ratio_fn}")

    def create_element_size_impact_plot(  # sizeofelement impact
        self, df: pd.DataFrame, ins_del_ratio_filter: Optional[float] = 0.01
    ):
        success_df = self._get_success_df(df)
        if success_df.empty or "element_size" not in success_df.columns:
            logger.warning("No data or 'element_size' for impact plot.")
            return

        filtered_df = success_df
        title_suffix = f" (Ins/Del: {ins_del_ratio_filter*100:.0f}%)"
        if ins_del_ratio_filter is not None and "ins_del_ratio" in filtered_df.columns:
            if any(
                np.isclose(filtered_df["ins_del_ratio"].unique(), ins_del_ratio_filter)
            ):
                filtered_df = filtered_df[
                    np.isclose(filtered_df["ins_del_ratio"], ins_del_ratio_filter)
                ]
            else:
                logger.warning(f"Ratio {ins_del_ratio_filter} not found. Using all.")
                title_suffix = " (Avg over Ins/Del Ratios)"
        if filtered_df.empty:
            logger.warning("No data after filtering for element size plot. Skipping.")
            return

        plot_data = (
            filtered_df.groupby(
                ["data_structure", "num_elements", "element_size", "random_access"]
            )[  # element_size is sizeofelement
                "ops_per_second"
            ]
            .mean()
            .reset_index()
        )
        if plot_data.empty:
            logger.warning("Aggregated data for element size plot empty.")
            return

        plot_hue_order = self._get_plot_order(plot_data["data_structure"].unique())

        g = sns.catplot(
            x="element_size",  # sizeofelement on x-axis
            y="ops_per_second",
            hue="data_structure",
            col="num_elements",  # Faceted by "size of elements"
            data=plot_data,
            kind="point",
            sharey=False,
            height=5,
            aspect=1.2,
            palette=self.palette,
            legend="full",  # Legend for data_structure
            hue_order=plot_hue_order,
        )
        g.set_axis_labels(
            "Element Size (Bytes)", "Mean Ops per Second"
        )  # sizeofelement
        g.set_titles(
            "Number of Elements: {col_name}"
        )  # Facet title indicates "size of elements"
        g.set(yscale="log")
        g.fig.suptitle(
            f"Impact of Element Size on Performance{title_suffix}", fontsize=16, y=1.03
        )
        for ax_g in g.axes.flat:
            for label in ax_g.get_xticklabels():
                label.set_rotation(45)
                label.set_horizontalalignment("right")
        self.save_plot(
            f"element_size_impact_ratio{str(ins_del_ratio_filter).replace('.', '_')}",
            fig=g.fig,
        )

    def create_performance_comparison_bars_categorized(self, df: pd.DataFrame):
        success_df = self._get_success_df(df)
        if success_df.empty:
            logger.warning("No data for categorized performance bars.")
            return
        
        success_df["structure_access"] = success_df["data_structure"] + success_df["random_access"].map({0: " (seq)", 1: " (rand)"})
        
        ds_categories = {
            "Basic": ["array", "linkedlist_seq", "linkedlist_rand"],
            "Unrolled": [
                ds for ds in success_df["data_structure"].unique() if "unrolled" in ds
            ],
            "Tiered": [
                ds for ds in success_df["data_structure"].unique() if "tiered" in ds
            ],
        }
        ds_categories = {
            k: v
            for k, v in ds_categories.items()
            if v and any(ds in success_df["data_structure"].unique() for ds in v)
        }
        if not ds_categories:
            logger.warning("No categories for categorized plot.")
            return

        num_categories = len(ds_categories)
        ncols = min(2, num_categories) if num_categories > 0 else 1
        nrows = (num_categories + ncols - 1) // ncols if num_categories > 0 else 1

        fig, axes = plt.subplots(
            nrows, ncols, figsize=(8 * ncols, 6 * nrows), squeeze=False
        )
        axes_flat = axes.flatten()
        fig.suptitle("Performance Comparison (Categorized)", fontsize=16)
        plot_made = False
        cat_idx = 0

        for category, structures_in_cat in ds_categories.items():
            if cat_idx >= len(axes_flat):
                break
            ax = axes_flat[cat_idx]
            cat_data = success_df[success_df["data_structure"].isin(structures_in_cat)]
            if cat_data.empty:
                ax.set_title(f"{category} (No Data)")
                ax.text(
                    0.5,
                    0.5,
                    "No data",
                    ha="center",
                    va="center",
                    transform=ax.transAxes,
                )
                cat_idx += 1
                continue

            perf_data = (
                cat_data.groupby(["structure_access", "num_elements"])["ops_per_second"]
                .mean()
                .reset_index()
            )
            pivot_data = perf_data.pivot(
                index="num_elements", columns="structure_access", values="ops_per_second"
            )
            if pivot_data.empty:
                ax.set_title(f"{category} (No Pivot Data)")
                cat_idx += 1
                continue

            ordered_cols_for_plot = [
                col
                for col in self._get_plot_order(pivot_data.columns.tolist())
                if col in pivot_data.columns
            ]
            pivot_data_to_plot = pivot_data[ordered_cols_for_plot]
            plot_colors = [
                self.ds_color_map.get(ds, self.default_color_for_pandas)
                for ds in ordered_cols_for_plot
            ]

            if not pivot_data_to_plot.empty:
                melted = pivot_data_to_plot.reset_index().melt(id_vars="num_elements", var_name="structure_access", value_name="ops_per_second")
                sns.barplot(
                    data=melted,
                    x="num_elements",
                    y="ops_per_second",
                    hue="structure_access",
                    ax=ax,
                    palette="tab20",
                )

                plot_made = True
            else:
                ax.set_title(f"{category} (No Data after ordering)")
                ax.text(
                    0.5,
                    0.5,
                    "No data",
                    ha="center",
                    va="center",
                    transform=ax.transAxes,
                )
                cat_idx += 1
                continue

            ax.set_title(f"{category} Data Structures")
            ax.set_xlabel("Number of Elements")  # This is "size of elements"
            ax.set_ylabel("Ops per Second (Log Scale)")
            ax.set_yscale("log")
            ax.legend(
                loc="upper right", fontsize="small", title=None
            )  # Legend for data_structure
            ax.tick_params(axis="x", rotation=45)
            ax.grid(True, which="both", ls="-", alpha=0.7)
            cat_idx += 1

        for j in range(cat_idx, nrows * ncols):
            if j < len(axes_flat):
                fig.delaxes(axes_flat[j])

        if plot_made:
            self.save_plot("performance_comparison_bars_categorized", fig=fig)
        else:
            plt.close(fig)

    def create_chunk_size_analysis(
        self, df: pd.DataFrame, element_size_filter: Optional[int] = None
    ):
        success_df = self._get_success_df(df)

        title_suffix = ""
        filename_suffix = ""
        if element_size_filter is not None:
            if (
                "element_size" in success_df.columns
                and element_size_filter in success_df["element_size"].unique()
            ):
                success_df = success_df[
                    success_df["element_size"] == element_size_filter
                ]
                title_suffix = f" (Element Size: {element_size_filter}B)"
                filename_suffix = f"_elemsize{element_size_filter}"
            else:
                logger.warning(
                    f"Element size {element_size_filter}B not found for chunk size analysis. "
                    "Averaging over all element sizes."
                )
                # If filter not found, fall back to averaging for this call
                title_suffix = " (Avg Element Size)"
                filename_suffix = "_elemsize_all"
        else:
            # Default behavior if no filter is specified: average over element sizes
            title_suffix = " (Avg Element Size)"
            filename_suffix = "_elemsize_all"
            # Note: Averaging here means not filtering by element_size.
            # The groupby later will handle aggregation if multiple element_sizes are present.

        if success_df.empty:
            logger.warning(f"No data for chunk size analysis{title_suffix}.")
            return

        fig, axes = plt.subplots(
            1, 2, figsize=(20, 7), sharey=True
        )  # Increased width for legend
        fig.suptitle(f"Chunk Size vs. Performance{title_suffix}", fontsize=16)
        plot_created = False

        # Unrolled linked lists
        unrolled_data = success_df[
            success_df["data_structure"].str.contains("unrolled", case=False, na=False)
        ].copy()
        if not unrolled_data.empty:
            unrolled_data["chunk_size"] = (
                unrolled_data["data_structure"]
                .str.extract(r"unrolled_linkedlist_(\d+)|unrolled_(\d+)")
                .bfill(axis=1)
                .iloc[:, 0]
                .astype(float)
            )
            unrolled_data.dropna(subset=["chunk_size"], inplace=True)
            unrolled_data["chunk_size"] = unrolled_data["chunk_size"].astype(int)

            if not unrolled_data.empty:
                # Aggregate considering num_elements and potentially multiple element_sizes if filter is None
                plot_df_unrolled = (
                    unrolled_data.groupby(["chunk_size", "num_elements"])[
                        "ops_per_second"
                    ]
                    .mean()
                    .reset_index()
                )
                if not plot_df_unrolled.empty:
                    sns.barplot(
                        x="chunk_size",
                        y="ops_per_second",
                        hue="num_elements",
                        data=plot_df_unrolled,
                        ax=axes[0],
                        palette=self.palette,  # Use main palette
                    )
                    axes[0].set_title("Unrolled Linked Lists")
                    axes[0].set_xlabel("Chunk Size")
                    axes[0].set_ylabel("Ops/sec (Log)")
                    axes[0].set_yscale("log")
                    axes[0].legend(
                        title="Number of Elements",
                        bbox_to_anchor=(1.02, 1),
                        loc="upper left",
                    )
                    plot_created = True
                else:
                    axes[0].set_title("Unrolled (No Aggregated Data)")
            else:
                axes[0].set_title("Unrolled (No Parsed Chunk Data)")
        else:
            axes[0].set_title("Unrolled (No Base Data)")

        # Tiered arrays
        tiered_data = success_df[
            success_df["data_structure"].str.contains(
                "tiered_array", case=False, na=False
            )
        ].copy()
        if not tiered_data.empty:
            tiered_data["chunk_size"] = (
                tiered_data["data_structure"]
                .str.extract(r"tiered_array_(\d+)")
                .iloc[:, 0]
                .astype(float)
            )
            tiered_data.dropna(subset=["chunk_size"], inplace=True)
            tiered_data["chunk_size"] = tiered_data["chunk_size"].astype(int)

            if not tiered_data.empty:
                plot_df_tiered = (
                    tiered_data.groupby(["chunk_size", "num_elements"])[
                        "ops_per_second"
                    ]
                    .mean()
                    .reset_index()
                )
                if not plot_df_tiered.empty:
                    sns.barplot(
                        x="chunk_size",
                        y="ops_per_second",
                        hue="num_elements",
                        data=plot_df_tiered,
                        ax=axes[1],
                        palette=self.palette,  # Use main palette
                    )
                    axes[1].set_title("Tiered Arrays")
                    axes[1].set_xlabel("Chunk Size")
                    axes[1].set_ylabel("")
                    axes[1].set_yscale("log")
                    axes[1].legend(
                        title="Number of Elements",
                        bbox_to_anchor=(1.02, 1),
                        loc="upper left",
                    )
                    plot_created = True
                else:
                    axes[1].set_title("Tiered (No Aggregated Data)")
            else:
                axes[1].set_title("Tiered (No Parsed Chunk Data)")
        else:
            axes[1].set_title("Tiered (No Base Data)")

        if plot_created:
            self.save_plot(f"chunk_size_analysis{filename_suffix}", fig=fig)
        else:
            plt.close(fig)

    def create_instruction_mix_analysis(self, df: pd.DataFrame):
        success_df = self._get_success_df(df)
        if success_df.empty or "ins_del_ratio" not in success_df.columns:
            logger.warning(
                "No successful data or 'ins_del_ratio' for instruction mix analysis."
            )
            return

        plot_data = (
            success_df.groupby(["data_structure", "num_elements", "ins_del_ratio"])[
                "ops_per_second"
            ]
            .mean()
            .reset_index()
        )
        if plot_data.empty:
            logger.warning("Aggregated data for instruction mix analysis is empty.")
            return

        plot_col_order = self._get_plot_order(plot_data["data_structure"].unique())
        num_ds = len(plot_col_order)
        col_wrap_val = min(3, num_ds) if num_ds > 0 else 1

        g = sns.catplot(
            x="ins_del_ratio",
            y="ops_per_second",
            hue="num_elements",  # Hue is "size of elements"
            col="data_structure",
            col_wrap=col_wrap_val,
            data=plot_data,
            kind="bar",
            sharey=False,
            height=4,
            aspect=1.3,
            palette="magma",
            legend="full",  # Seaborn will use hue name for title
            col_order=plot_col_order,
        )
        if g.legend:  # Set explicit title for clarity
            g.legend.set_title("Number of Elements")

        g.set_axis_labels("Insert/Delete Ratio (%)", "Mean Ops per Second")
        g.set_titles("{col_name}")  # Facet title is data_structure
        g.set(yscale="log")
        g.fig.suptitle("Performance vs. Instruction Mix", fontsize=16, y=1.02)

        for ax_g in g.axes.flat:
            if not ax_g.get_xticklabels():
                continue
            current_labels = ax_g.get_xticklabels()
            new_labels = []
            for t in current_labels:
                label_text = t.get_text()
                if label_text and label_text.strip():
                    try:
                        new_labels.append(f"{float(label_text) * 100:.0f}%")
                    except ValueError:
                        new_labels.append(label_text)
                else:
                    new_labels.append(label_text)
            if new_labels:
                ax_g.set_xticklabels(new_labels)
        self.save_plot("instruction_mix_analysis", fig=g.fig)

    def create_memory_efficiency_plot(self, df: pd.DataFrame):
        success_df = self._get_success_df(df)
        if success_df.empty or "peak_memory_mb" not in success_df.columns:
            logger.warning(
                "No successful data or 'peak_memory_mb' for memory efficiency plot."
            )
            return

        fig, axes = plt.subplots(1, 2, figsize=(18, 7))
        fig.suptitle("Memory Usage and Efficiency", fontsize=16)

        mem_data_avg = (
            success_df.groupby(["data_structure", "num_elements"])["peak_memory_mb"]
            .mean()
            .reset_index()
        )
        if not mem_data_avg.empty:
            plot_hue_order = self._get_plot_order(
                mem_data_avg["data_structure"].unique()
            )
            sns.lineplot(
                data=mem_data_avg,
                x="num_elements",
                y="peak_memory_mb",
                hue="data_structure",
                style="data_structure",
                markers=True,
                dashes=False,
                ax=axes[0],
                palette=self.palette,
                hue_order=plot_hue_order,
            )
            axes[0].set_xscale("log")
            axes[0].set_yscale("log")
            axes[0].set_title("Memory Usage vs Data Size")
            axes[0].set_xlabel(
                "Number of Elements (Log Scale)"
            )  # "size of elements" on x-axis
            axes[0].set_ylabel("Peak Memory (MB) (Log Scale)")
            axes[0].legend(  # Legend for data_structure
                title="Data Structure", fontsize="small", loc="upper left"
            )
            axes[0].grid(True, which="both", ls="-", alpha=0.7)
        else:
            axes[0].set_title("Memory Usage vs Data Size (No Data)")

        efficiency_data = success_df.copy()
        efficiency_data = efficiency_data[efficiency_data["peak_memory_mb"] > 0.01]
        if not efficiency_data.empty and "ops_per_second" in efficiency_data.columns:
            efficiency_data["ops_per_mb"] = (
                efficiency_data["ops_per_second"] / efficiency_data["peak_memory_mb"]
            )
            eff_grouped = (
                efficiency_data.groupby("data_structure")["ops_per_mb"]
                .mean()
                .reset_index()
            )
            eff_grouped_sorted = eff_grouped.sort_values("ops_per_mb", ascending=False)

            if not eff_grouped_sorted.empty:
                bar_color = "#F8766D"
                sns.barplot(
                    x="ops_per_mb",
                    y="data_structure",
                    data=eff_grouped_sorted,
                    ax=axes[1],
                    color=bar_color,
                    orient="h",
                )
                axes[1].set_title("Memory Efficiency (Ops/sec per MB)")
                axes[1].set_xlabel("Operations per Second per MB")
                axes[1].set_ylabel("Data Structure")
            else:
                axes[1].set_title("Memory Efficiency (Ops/sec per MB) (No Data)")
        else:
            axes[1].set_title("Memory Efficiency (Ops/sec per MB) (No Data)")
        self.save_plot("memory_usage_and_efficiency", fig=fig)

    def create_scalability_analysis(self, df: pd.DataFrame):
        success_df = self._get_success_df(df)
        if success_df.empty:
            logger.warning("No successful data for scalability analysis.")
            return

        perf_by_size_ds = (
            success_df.groupby(["data_structure", "num_elements"])["ops_per_second"]
            .mean()
            .reset_index()
        )
        scalability_data = []
        for ds_name, group in perf_by_size_ds.groupby("data_structure"):
            group = group.sort_values("num_elements")
            if not group.empty and len(group) > 1:
                baseline_perf = group["ops_per_second"].iloc[0]
                if baseline_perf > 0:
                    for _, row in group.iterrows():
                        scalability_data.append(
                            {
                                "data_structure": ds_name,
                                "num_elements": row["num_elements"],
                                "performance_ratio": row["ops_per_second"]
                                / baseline_perf,
                            }
                        )
        if not scalability_data:
            logger.warning("Not enough data points to calculate scalability ratios.")
            return

        scalability_df = pd.DataFrame(scalability_data)
        plot_hue_order = self._get_plot_order(scalability_df["data_structure"].unique())

        plt.figure(figsize=(14, 8))
        sns.lineplot(
            data=scalability_df,
            x="num_elements",  # "size of elements" on x-axis
            y="performance_ratio",
            hue="data_structure",
            style="data_structure",
            markers=True,
            dashes=False,
            palette=self.palette,
            hue_order=plot_hue_order,
            linewidth=2.5,
        )
        plt.xscale("log")
        plt.title("Performance Scalability (Relative to Smallest Dataset)", fontsize=16)
        plt.xlabel("Number of Elements (Log Scale)", fontsize=14)
        plt.ylabel("Performance Ratio", fontsize=14)
        plt.axhline(
            1.0, color="grey", linestyle="--", label="Baseline Performance Level"
        )
        plt.legend(  # Legend for data_structure
            title="Data Structure",
            bbox_to_anchor=(0.01, 0.01),
            loc="lower left",
            ncol=1,
        )
        plt.grid(True, which="both", ls=":", alpha=0.5)
        self.save_plot("scalability_analysis")

    def create_all_plots(self, df: pd.DataFrame):
        if df.empty:
            logger.error("Input DataFrame is empty. No plots will be generated.")
            return

        logger.info("Generating plots...")
        self.create_performance_comparison_unified_bars(df.copy())
        self.create_performance_relative_to_baseline_array(df.copy())

        # Existing heatmaps
        self.create_performance_heatmap(
            df.copy(), element_size_filter=512, ins_del_ratio_filter=0.01
        )
        self.create_performance_heatmap(
            df.copy(), element_size_filter=64, ins_del_ratio_filter=0.0
        )
        # New heatmap for 50% insert/delete, averaging over element sizes
        self.create_performance_heatmap(
            df.copy(), element_size_filter=None, ins_del_ratio_filter=0.5
        )

        self.create_element_size_impact_plot(df.copy(), ins_del_ratio_filter=0.01)
        self.create_performance_comparison_bars_categorized(df.copy())
        self.create_chunk_size_analysis(df.copy(), element_size_filter=None)  # Average
        self.create_chunk_size_analysis(
            df.copy(), element_size_filter=64
        )  # Example for 64B elements
        self.create_chunk_size_analysis(
            df.copy(), element_size_filter=512
        )  # Example for 512B elements
        self.create_instruction_mix_analysis(df.copy())
        self.create_memory_efficiency_plot(df.copy())
        self.create_scalability_analysis(df.copy())

        logger.info(f"All plots saved to {self.plots_dir.resolve()}")
