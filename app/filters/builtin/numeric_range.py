"""Numeric range filter plugin."""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.filters.base import Filter, filter_registry


@filter_registry.register("numeric_range")
class NumericRangeFilter(Filter):
    """Filter that selects rows where a numeric column falls within [min, max]."""

    @property
    def name(self) -> str:
        """Return the unique name of the filter."""
        return "numeric_range"

    @property
    def description(self) -> str:
        """Return a brief description of what the filter does."""
        return (
            "Filters rows where a numeric column falls within a specified "
            "range [min, max]. At least one of 'min' or 'max' must be provided."
        )

    def validate_params(self, params: dict[str, Any]) -> None:
        """Validate parameters for the numeric range filter.

        Args:
            params: The parameters dictionary.

        Raises:
            ValueError: If parameters are invalid.
        """
        if "column" not in params:
            msg = "Missing required parameter: 'column'"
            raise ValueError(msg)
        if not isinstance(params["column"], str):
            col_type = type(params["column"]).__name__
            msg = f"Parameter 'column' must be a string, got {col_type}"
            raise ValueError(msg)

        has_min = "min" in params and params["min"] is not None
        has_max = "max" in params and params["max"] is not None

        if not has_min and not has_max:
            msg = "At least one of 'min' or 'max' must be provided and not None."
            raise ValueError(msg)

        min_val = None
        max_val = None

        if has_min:
            min_val = params["min"]
            if not isinstance(min_val, (int, float)):
                msg = f"Parameter 'min' must be numeric, got {type(min_val).__name__}"
                raise ValueError(msg)

        if has_max:
            max_val = params["max"]
            if not isinstance(max_val, (int, float)):
                msg = f"Parameter 'max' must be numeric, got {type(max_val).__name__}"
                raise ValueError(msg)

        if has_min and has_max and min_val is not None and max_val is not None and min_val > max_val:
            msg = f"Parameter 'min' ({min_val}) cannot be greater than 'max' ({max_val})."
            raise ValueError(msg)

    def apply(self, df: pd.DataFrame, params: dict[str, Any]) -> pd.DataFrame:
        """Apply the numeric range filter to the given DataFrame.

        Args:
            df: The DataFrame to filter.
            params: The parameters dictionary.

        Returns:
            The filtered DataFrame.

        Raises:
            ValueError: If the column is missing or not numeric.
        """
        column = params["column"]
        if column not in df.columns:
            msg = f"Column {column!r} not found in DataFrame."
            raise ValueError(msg)

        # Check if the column dtype is numeric
        if not pd.api.types.is_numeric_dtype(df[column]):
            msg = f"Column {column!r} must be numeric, got dtype {df[column].dtype}"
            raise ValueError(msg)

        # Apply filtering
        result_df = df
        if "min" in params and params["min"] is not None:
            result_df = result_df[result_df[column] >= params["min"]]
        if "max" in params and params["max"] is not None:
            result_df = result_df[result_df[column] <= params["max"]]

        return result_df
