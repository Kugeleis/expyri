from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

from app.core.session import HierarchyConfig


@dataclass
class HierarchicalData:
    """Container for hierarchical dataset structure."""

    unit_df: pd.DataFrame
    cluster_agg: pd.DataFrame
    config: HierarchyConfig
    excluded_clusters: list[str]
    metric: str
    metric_kind: Literal["continuous", "binary_proportion", "unsupported"]
    icc: float | None = None
