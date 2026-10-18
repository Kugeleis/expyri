"""Plot selection and generation helpers for wizard sessions."""

from __future__ import annotations

import inspect
from typing import Any

import pandas as pd

from app.core.session import WizardSession
from app.plots.base import PlotResult, plot_registry
from app.stats.properties import compute_properties
from app.wizard.statistics import significance_p_value


def select_top_plot_columns(
    session: WizardSession,
    plots_sig_filter: float,
    top_n_columns: int | None = None,
) -> list[str]:
    """Select columns that should be plotted from stored statistical results."""
    if session.stat_results:
        if top_n_columns is not None:
            ranked_cols = [res["column_name"] for res in session.stat_results if "column_name" in res]
            return [col for col in ranked_cols if col and col in session.selected_value_columns][:top_n_columns]
        return [
            res["column_name"]
            for res in session.stat_results
            if "column_name" in res
            and (p_value := significance_p_value(res)) is not None
            and p_value <= plots_sig_filter
        ]
    return session.selected_value_columns[:top_n_columns] if top_n_columns is not None else []


def generate_individual_plots(
    session: WizardSession,
    filtered_df: pd.DataFrame,
    top_columns: list[str],
    selected_plots: list[str],
    theme: str = "dark",
) -> list[PlotResult]:
    """Call applicable plot generators and collect results."""
    plot_results: list[PlotResult] = []

    for value_col in top_columns:
        props = compute_properties(session, filtered_df, value_col)
        applicable = plot_registry.get_applicable(props)
        for name in selected_plots:
            if name not in applicable:
                continue
            generator = plot_registry.get(name)

            sig = inspect.signature(generator.generate)
            accepts_var_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
            kwargs: dict[str, Any] = {}
            if "theme" in sig.parameters or accepts_var_kwargs:
                kwargs["theme"] = theme
            is_hier = "hierarchy" in sig.parameters or accepts_var_kwargs
            if is_hier:
                kwargs["hierarchy"] = session.hierarchy
                kwargs["excluded_clusters"] = [ex.cluster_id for ex in session.excluded_clusters]

            plot_result = generator.generate(filtered_df, session.group_column or "", value_col, **kwargs)
            plot_result.column_name = value_col
            plot_results.append(plot_result)
    return plot_results
