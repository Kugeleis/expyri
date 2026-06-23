"""Dataset utilities."""

from __future__ import annotations

import pandas as pd


def resolve_selected_value_columns(df: pd.DataFrame, group_column: str, selected_value_columns: list[str]) -> list[str]:
    """Resolve and validate continuous/numeric value columns to analyze."""
    if selected_value_columns:
        missing = [col for col in selected_value_columns if col not in df.columns]
        if missing:
            raise ValueError(f"Selected value columns not found in dataset: {missing}")
        if group_column in selected_value_columns:
            raise ValueError("Group column must not appear in selected value columns.")
        non_numeric = [col for col in selected_value_columns if not pd.api.types.is_numeric_dtype(df[col])]
        if non_numeric:
            raise ValueError(f"Selected value columns must be numeric. Non-numeric columns: {non_numeric}")
        return selected_value_columns

    numeric_columns = [col for col in df.select_dtypes(include=["number"]).columns if col != group_column]
    return numeric_columns


def resolve_selected_discrete_columns(
    df: pd.DataFrame, group_column: str, selected_discrete_columns: list[str]
) -> list[str]:
    """Resolve and validate discrete/non-numeric columns to analyze."""
    if selected_discrete_columns:
        missing = [col for col in selected_discrete_columns if col not in df.columns]
        if missing:
            raise ValueError(f"Selected discrete columns not found in dataset: {missing}")
        if group_column in selected_discrete_columns:
            raise ValueError("Group column must not appear in selected discrete columns.")
        numeric = [col for col in selected_discrete_columns if pd.api.types.is_numeric_dtype(df[col])]
        if numeric:
            raise ValueError(f"Selected discrete columns must be categorical/non-numeric. Numeric columns: {numeric}")
        return selected_discrete_columns

    discrete_columns = [col for col in df.columns if not pd.api.types.is_numeric_dtype(df[col]) and col != group_column]
    return discrete_columns
