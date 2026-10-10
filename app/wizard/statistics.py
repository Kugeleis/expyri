"""Statistical execution helpers for wizard sessions."""

from __future__ import annotations

from typing import Literal

import pandas as pd
from fastapi import HTTPException

from app.core.session import WizardSession
from app.datasets.hierarchical import HierarchicalData
from app.stats.base import StatMethod, StatResult
from app.stats.properties import build_cluster_aggregates, compute_quick_icc


def run_stat_for_column(
    filtered_df: pd.DataFrame,
    value_col: str,
    method: StatMethod,
    session: WizardSession,
) -> StatResult:
    """Run a statistical method on one column for flat or hierarchical data."""
    if session.hierarchy is not None:
        res = _run_hierarchical_stat(filtered_df, value_col, method, session)
    else:
        res = _run_flat_stat(filtered_df, value_col, method, session)

    res.column_name = value_col
    return res


def _run_hierarchical_stat(
    filtered_df: pd.DataFrame,
    value_col: str,
    method: StatMethod,
    session: WizardSession,
) -> StatResult:
    unique_vals = set(filtered_df[value_col].dropna().unique())
    is_bin = unique_vals.issubset({0, 1}) and len(unique_vals) > 0
    is_num = pd.api.types.is_numeric_dtype(filtered_df[value_col]) or pd.api.types.is_bool_dtype(filtered_df[value_col])
    metric_kind: Literal["continuous", "binary_proportion", "unsupported"] = (
        "binary_proportion" if is_bin else ("continuous" if is_num else "unsupported")
    )
    if metric_kind == "unsupported":
        raise HTTPException(
            status_code=400,
            detail=f"Column {value_col!r} is not supported in hierarchical mode.",
        )

    hierarchy = session.hierarchy
    if hierarchy is None:
        raise HTTPException(status_code=400, detail="Hierarchical mode is not enabled")

    excluded_ids = [ex.cluster_id for ex in session.excluded_clusters]
    cluster_agg = build_cluster_aggregates(filtered_df, hierarchy, excluded_ids, value_col, metric_kind)
    clean_unit = filtered_df[~filtered_df[hierarchy.cluster_col].astype(str).isin(excluded_ids)]
    icc = compute_quick_icc(clean_unit, hierarchy.cluster_col, value_col)
    h_data = HierarchicalData(
        unit_df=filtered_df,
        cluster_agg=cluster_agg,
        config=hierarchy,
        excluded_clusters=excluded_ids,
        metric=value_col,
        metric_kind=metric_kind,
        icc=icc,
    )
    try:
        return method.run(h_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


def _run_flat_stat(
    filtered_df: pd.DataFrame,
    value_col: str,
    method: StatMethod,
    session: WizardSession,
) -> StatResult:
    if session.group_column is None:
        raise HTTPException(status_code=400, detail="Group column is not selected")

    grouped = filtered_df.groupby(session.group_column)[value_col]
    group_data = {str(name): list(group.dropna().values) for name, group in grouped}
    try:
        return method.run(group_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
