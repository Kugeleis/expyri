"""Statistical method base classes and utilities.

All statistical methods must inherit from ``StatMethod`` and register
themselves using the global ``stat_registry``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd
import scipy.stats as stats
from pydantic import BaseModel, Field

from app.core.registry import Registry


class DataProperties(BaseModel):
    """Properties characterizing a dataset for statistical method applicability."""

    n_groups: int = Field(..., description="Number of distinct groups.")
    group_sizes: dict[str, int] = Field(
        ..., description="Size of each group after removing NaNs."
    )
    normality: dict[str, float] = Field(
        ..., description="Shapiro-Wilk normality test p-value for each group."
    )
    variance_homogeneity: float = Field(
        ..., description="Levene's test p-value for variance homogeneity."
    )


class StatResult(BaseModel):
    """The result of executing a statistical method."""

    method_name: str = Field(..., description="Name of the statistical method.")
    test_statistic: float = Field(..., description="Calculated test statistic.")
    p_value: float = Field(..., description="Calculated p-value.")
    effect_size: float | None = Field(
        None, description="Optional calculated effect size."
    )
    summary: str = Field(..., description="Human-readable text summary of results.")


class StatMethod(ABC):
    """Abstract base class for all statistical evaluation methods."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the unique name of the statistical method."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Return a brief description of the statistical method."""
        ...

    @abstractmethod
    def is_applicable(self, **properties: Any) -> bool:
        """Determine whether this method is applicable to the given data properties.

        Args:
            **properties: Keyword arguments representing data properties.

        Returns:
            True if the method can be run on this data, False otherwise.
        """
        ...

    @abstractmethod
    def run(self, groups: dict[str, list[float]]) -> StatResult:
        """Run the statistical method on the grouped data.

        Args:
            groups: A dictionary mapping group names to lists of numeric values.

        Returns:
            A StatResult containing the test statistic, p-value, etc.
        """
        ...


stat_registry: Registry[StatMethod] = Registry("stat")


def compute_data_properties(
    df: pd.DataFrame, group_col: str, value_col: str
) -> DataProperties:
    """Compute properties of the data to evaluate statistical test applicability.

    Args:
        df: The dataset DataFrame.
        group_col: Column name representing the groups (independent variable).
        value_col: Column name representing the values (dependent variable).

    Returns:
        A DataProperties object.

    Raises:
        ValueError: If columns are missing or values column is not numeric.
    """
    if group_col not in df.columns:
        msg = f"Group column {group_col!r} not found in DataFrame."
        raise ValueError(msg)
    if value_col not in df.columns:
        msg = f"Value column {value_col!r} not found in DataFrame."
        raise ValueError(msg)

    if not pd.api.types.is_numeric_dtype(df[value_col]):
        val_dtype = df[value_col].dtype
        msg = f"Value column {value_col!r} must be numeric, got dtype {val_dtype}"
        raise ValueError(msg)

    # Drop rows where group or value is NaN
    clean_df = df[[group_col, value_col]].dropna()

    grouped = clean_df.groupby(group_col)[value_col]
    group_sizes: dict[str, int] = {}
    normality: dict[str, float] = {}
    group_arrays: list[Any] = []

    for name, group_series in grouped:
        name_str = str(name)
        vals = group_series.tolist()
        group_sizes[name_str] = len(vals)
        group_arrays.append(group_series.values)

        if len(vals) >= 3:
            try:
                _, p_val = stats.shapiro(vals)
                normality[name_str] = float(p_val)
            except Exception:
                normality[name_str] = 0.0
        else:
            normality[name_str] = 0.0

    n_groups = len(group_sizes)

    # Compute Levene's test for variance homogeneity if there are >= 2 groups
    if n_groups >= 2 and all(len(arr) > 0 for arr in group_arrays):
        try:
            _, levene_p = stats.levene(*group_arrays)
            variance_homogeneity = float(levene_p)
        except Exception:
            variance_homogeneity = 0.0
    else:
        variance_homogeneity = 0.0

    return DataProperties(
        n_groups=n_groups,
        group_sizes=group_sizes,
        normality=normality,
        variance_homogeneity=variance_homogeneity,
    )
