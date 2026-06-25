from __future__ import annotations

from typing import Any

import pandas as pd

from app.filters.base import Filter, filter_registry
from app.stats.models import DataProperties


@filter_registry.register("cluster_exclusion")
class ClusterExclusionFilter(Filter):
    """Excludes specific clusters from analysis.

    Requires a non-empty reason string for each exclusion (audit trail).
    Applicable whenever hierarchy config is present.
    """

    @property
    def name(self) -> str:
        """Return the unique name of the filter."""
        return "cluster_exclusion"

    @property
    def description(self) -> str:
        """Return a brief description of what the filter does."""
        return "Excludes specific clusters from analysis with an audit trail reason."

    def is_applicable(self, properties: DataProperties) -> bool:
        """Determine whether this filter is applicable given data properties."""
        return bool(properties.has_hierarchy)

    def validate_params(self, params: dict[str, Any]) -> None:
        """Validate the parameters for this filter."""
        exclusions = params.get("exclusions")
        if exclusions is None:
            raise ValueError("Missing 'exclusions' parameter.")
        if not isinstance(exclusions, list):
            raise ValueError("'exclusions' must be a list.")
        for item in exclusions:
            if not isinstance(item, dict):
                raise ValueError("Each exclusion must be a dictionary.")
            if "cluster_id" not in item:
                raise ValueError("Each exclusion must have a 'cluster_id'.")
            reason = item.get("reason")
            if not reason or not isinstance(reason, str) or not reason.strip():
                raise ValueError("Each exclusion must have a non-empty 'reason'.")

    def apply(self, df: pd.DataFrame, params: dict[str, Any]) -> pd.DataFrame:
        """Apply the filter to the given DataFrame."""
        # Does not modify unit_df in place — it passes the exclusion list through
        # to HierarchicalData so stat methods can honour it.
        return df
