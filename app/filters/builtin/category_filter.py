"""Category filter plugin."""

from __future__ import annotations

from typing import Any, cast

import pandas as pd

from app.filters.base import Filter, filter_registry


@filter_registry.register("category_filter")
class CategoryFilter(Filter):
    """Filter that includes or excludes rows based on a list of categories."""

    @property
    def name(self) -> str:
        """Return the unique name of the filter."""
        return "category_filter"

    @property
    def description(self) -> str:
        """Return a brief description of what the filter does."""
        return "Filters rows by matching values in a categorical column (include or exclude)."

    def validate_params(self, params: dict[str, Any]) -> None:
        """Validate parameters for the category filter.

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

        if "values" not in params:
            msg = "Missing required parameter: 'values'"
            raise ValueError(msg)
        if not isinstance(params["values"], list):
            val_type = type(params["values"]).__name__
            msg = f"Parameter 'values' must be a list, got {val_type}"
            raise ValueError(msg)

        mode = params.get("mode", "include")
        if mode not in ("include", "exclude"):
            msg = f"Parameter 'mode' must be either 'include' or 'exclude', got {mode!r}"
            raise ValueError(msg)

    def apply(self, df: pd.DataFrame, params: dict[str, Any]) -> pd.DataFrame:
        """Apply the category filter to the given DataFrame.

        Args:
            df: The DataFrame to filter.
            params: The parameters dictionary.

        Returns:
            The filtered DataFrame.

        Raises:
            ValueError: If the column is missing.
        """
        column = params["column"]
        if column not in df.columns:
            msg = f"Column {column!r} not found in DataFrame."
            raise ValueError(msg)

        values = params["values"]
        mode = params.get("mode", "include")

        if mode == "include":
            return cast(pd.DataFrame, df[df[column].isin(values)])
        # mode == "exclude"
        return cast(pd.DataFrame, df[~df[column].isin(values)])
