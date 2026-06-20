"""Filter abstract base class and pipeline execution.

All builtin and custom data filters must inherit from the ``Filter`` ABC
and register themselves using the global ``filter_registry``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd

from app.core.registry import Registry


class Filter(ABC):
    """Abstract base class for all dataset filters."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the unique name of the filter.

        This name is used to identify and lookup the filter in the registry.
        """
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Return a brief description of what the filter does."""
        ...

    @abstractmethod
    def apply(self, df: pd.DataFrame, params: dict[str, Any]) -> pd.DataFrame:
        """Apply the filter to the given DataFrame.

        Args:
            df: The DataFrame to filter.
            params: Parameters configuring the filter.

        Returns:
            The filtered DataFrame.
        """
        ...

    @abstractmethod
    def validate_params(self, params: dict[str, Any]) -> None:
        """Validate the parameters for this filter.

        Args:
            params: The parameters to validate.

        Raises:
            ValueError: If the parameters are invalid.
        """
        ...


filter_registry: Registry[Filter] = Registry("filter")


def apply_filter_pipeline(
    df: pd.DataFrame, filter_configs: list[dict[str, Any]]
) -> pd.DataFrame:
    """Apply a sequence of filter configurations to a DataFrame.

    Each configuration is a dictionary specifying the filter "name"
    and its "params" dictionary.

    Args:
        df: The input DataFrame.
        filter_configs: The list of filter configurations.

    Returns:
        The filtered DataFrame after applying all filters in sequence.

    Raises:
        ValueError: If a configuration lacks a name, or if validation fails.
    """
    current_df = df.copy()
    for config in filter_configs:
        name = config.get("name")
        if not name:
            msg = "Filter configuration must contain a 'name' field."
            raise ValueError(msg)

        params = config.get("params", {})
        if not isinstance(params, dict):
            msg = f"Filter 'params' must be a dictionary, got {type(params).__name__}"
            raise ValueError(msg)

        filter_inst = filter_registry.get(name)
        filter_inst.validate_params(params)
        current_df = filter_inst.apply(current_df, params)

    return current_df
