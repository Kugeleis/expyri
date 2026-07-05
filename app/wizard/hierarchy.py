"""Hierarchy configuration helpers for the wizard workflow."""

from __future__ import annotations

from typing import Any

import pandas as pd
from fastapi import HTTPException

from app.core.session import HierarchyConfig, WizardSession


def validate_cluster_col(schema: Any, group_column: str, cluster_col: str) -> None:
    """Validate hierarchical cluster column constraints."""
    if cluster_col == group_column:
        raise HTTPException(
            status_code=400,
            detail="Cluster column must not be the same as the group column.",
        )
    cluster_col_info = next((col for col in schema.columns or [] if col.name == cluster_col), None)
    if not cluster_col_info:
        raise HTTPException(status_code=400, detail=f"Cluster column {cluster_col!r} not found")
    if cluster_col_info.is_numeric:
        raise HTTPException(
            status_code=400,
            detail=f"Cluster column {cluster_col!r} must be discrete/categorical, but it is numeric.",
        )


def filter_hierarchical_columns(
    session: WizardSession,
    df: pd.DataFrame,
    group_column: str,
    cluster_col: str,
    unit_col: str | None,
    x_col: str | None,
    y_col: str | None,
    selected_value_columns: list[str],
    selected_discrete_columns: list[str],
) -> None:
    """Filter selected columns by hierarchy mapping and type checks."""
    ignored_cols = {group_column, cluster_col}
    if unit_col:
        ignored_cols.add(unit_col)
    if x_col:
        ignored_cols.add(x_col)
    if y_col:
        ignored_cols.add(y_col)

    session.selected_value_columns = [
        col
        for col in selected_value_columns
        if col not in ignored_cols
        and col in df.columns
        and (pd.api.types.is_numeric_dtype(df[col]) or pd.api.types.is_bool_dtype(df[col]))
    ]

    new_disc = []
    for col in selected_discrete_columns:
        if col in ignored_cols or col not in df.columns:
            continue
        if pd.api.types.is_numeric_dtype(df[col]) or pd.api.types.is_bool_dtype(df[col]):
            unique_vals = set(df[col].dropna().unique())
            if unique_vals.issubset({0, 1}):
                new_disc.append(col)
    session.selected_discrete_columns = new_disc


def setup_hierarchy(
    session: WizardSession,
    schema: Any,
    df: pd.DataFrame,
    group_column: str,
    cluster_col: str,
    selected_clusters: list[str],
    unit_col: str | None,
    x_col: str | None,
    y_col: str | None,
    selected_value_columns: list[str],
    selected_discrete_columns: list[str],
) -> None:
    """Configure and validate hierarchical settings on a session."""
    validate_cluster_col(schema, group_column, cluster_col)

    session.hierarchy = HierarchyConfig(
        group_col=group_column,
        cluster_col=cluster_col,
        selected_clusters=selected_clusters,
        unit_col=unit_col,
        x_col=x_col,
        y_col=y_col,
    )

    filter_hierarchical_columns(
        session,
        df,
        group_column,
        cluster_col,
        unit_col,
        x_col,
        y_col,
        selected_value_columns,
        selected_discrete_columns,
    )
