"""Filtering helpers for wizard sessions."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pandas as pd
from fastapi import HTTPException

from app.core.session import ClusterExclusion, WizardSession
from app.datasets.repository import DatasetRepository
from app.filters.base import apply_filter_pipeline
from app.filters.models import FilterConfig


def build_filter_config(
    filter_type: str,
    column: str,
    min_val: str | None = None,
    max_val: str | None = None,
    values: str | None = None,
    exclude: bool = False,
    cluster_id: str | None = None,
    reason: str | None = None,
) -> FilterConfig:
    """Build a validated filter configuration from form inputs."""
    params: dict[str, Any] = {}
    if filter_type == "numeric_range":
        params["column"] = column
        params["min"] = float(min_val) if min_val else None
        params["max"] = float(max_val) if max_val else None
    elif filter_type == "category_filter":
        params["column"] = column
        params["values"] = [v.strip() for v in values.split(",")] if values else []
        params["mode"] = "exclude" if exclude else "include"
    elif filter_type == "cluster_exclusion":
        if not cluster_id or not reason:
            raise HTTPException(status_code=400, detail="Cluster ID and Reason are required")
        params["exclusions"] = [{"cluster_id": cluster_id, "reason": reason}]
    else:
        raise HTTPException(status_code=400, detail="Invalid filter type")

    return FilterConfig(name=filter_type, column=column, params=params)


def extract_cluster_exclusions(filters_config: Sequence[FilterConfig]) -> list[ClusterExclusion]:
    """Return session exclusion records represented by cluster-exclusion filters."""
    excluded = []
    for filter_config in filters_config:
        if filter_config.name == "cluster_exclusion":
            exclusions_list = filter_config.params.get("exclusions", [])
            for item in exclusions_list:
                excluded.append(ClusterExclusion(cluster_id=str(item["cluster_id"]), reason=str(item["reason"])))
    return excluded


def get_filtered_df_with_groups(session: WizardSession, repo: DatasetRepository) -> pd.DataFrame:
    """Load a session dataset, apply filters, and narrow to selected groups/clusters."""
    if not session.dataset_id:
        raise HTTPException(status_code=400, detail="Dataset not selected")

    try:
        df = repo.load_dataset(session.dataset_id)
    except KeyError:
        raise HTTPException(status_code=400, detail="Dataset missing") from None

    filtered_df = apply_filter_pipeline(df, session.filters_config)
    if session.group_column and session.selected_groups:
        filtered_df = filtered_df[filtered_df[session.group_column].astype(str).isin(session.selected_groups)]
    if session.hierarchy and session.hierarchy.selected_clusters:
        filtered_df = filtered_df[
            filtered_df[session.hierarchy.cluster_col].astype(str).isin(session.hierarchy.selected_clusters)
        ]
    return filtered_df
