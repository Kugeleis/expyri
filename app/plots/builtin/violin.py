"""Violin plot generator plugin."""

from __future__ import annotations

import base64
import io
from typing import TYPE_CHECKING, Any

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd

from app.plots.base import PlotGenerator, PlotResult, plot_registry

matplotlib.use("Agg")

if TYPE_CHECKING:
    pass


@plot_registry.register("violinplot")
class ViolinPlot(PlotGenerator):
    """Violin plot generator plugin."""

    @property
    def name(self) -> str:
        """Return the unique name of the plot generator."""
        return "violinplot"

    @property
    def description(self) -> str:
        """Return a brief description of what the plot displays."""
        return "Violin plot of values grouped by category."

    def is_applicable(self, **properties: Any) -> bool:
        """Determine whether the violin plot is applicable.

        Requires at least 1 group, and all groups with size >= 3 (for KDE).
        """
        n_groups = properties.get("n_groups", 0)
        group_sizes = properties.get("group_sizes", {})
        if n_groups < 1:
            return False
        return all(size >= 3 for size in group_sizes.values())

    def generate(self, df: pd.DataFrame, group_col: str, value_col: str) -> PlotResult:
        """Generate a violin plot.

        Args:
            df: The dataset DataFrame.
            group_col: Column name representing the groups.
            value_col: Column name representing the values.

        Returns:
            A PlotResult.
        """
        groups = sorted(df[group_col].dropna().unique())
        data = [df[df[group_col] == g][value_col].dropna().values for g in groups]

        fig, ax = plt.subplots()
        try:
            ax.violinplot(data)
            ax.set_xticks(range(1, len(groups) + 1))
            ax.set_xticklabels(groups)
            ax.set_title(f"Violin Plot of {value_col} by {group_col}")
            ax.set_xlabel(group_col)
            ax.set_ylabel(value_col)

            buf = io.BytesIO()
            fig.savefig(buf, format="png", bbox_inches="tight")
            buf.seek(0)
            image_base64 = base64.b64encode(buf.read()).decode("utf-8")
        finally:
            plt.close(fig)

        return PlotResult(
            plot_type=self.name,
            image_base64=image_base64,
            content_type="image/png",
        )
