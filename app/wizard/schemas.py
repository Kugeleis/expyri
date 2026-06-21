"""Wizard request/response Pydantic schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DatasetSelectionRequest(BaseModel):
    """Payload for selecting a dataset and mapping columns."""

    dataset_id: str = Field(..., description="ID of the selected dataset.")
    group_column: str = Field(..., description="Column mapping for grouping (independent variable).")
    selected_value_columns: list[str] = Field(
        default_factory=list,
        description=(
            "List of dependent variable columns to analyze. "
            "If omitted or empty, all numeric columns except the "
            "group column are used by default."
        ),
    )
    selected_groups: list[str] = Field(
        default_factory=list,
        description="List of selected subgroup values to include in the analysis.",
    )


class FilterConfigEntry(BaseModel):
    """A single filter configuration."""

    name: str = Field(..., description="Name of the filter plugin.")
    params: dict[str, Any] = Field(default_factory=dict, description="Configuration parameters.")


class FiltersConfigRequest(BaseModel):
    """Payload for configuring preprocessing filters."""

    filters_config: list[FilterConfigEntry] = Field(..., description="Sequence of filters to apply.")


class MethodSelectionRequest(BaseModel):
    """Payload for selecting a statistical method."""

    selected_method: str = Field(..., description="Name of the selected statistical method plugin.")


class PlotSelectionRequest(BaseModel):
    """Payload for selecting plot generators."""

    selected_plots: list[str] = Field(..., description="List of plot names to generate.")
    top_n_columns: int = Field(
        1,
        description=("Number of top-ranked variables to plot, sorted by statistical significance."),
        ge=1,
    )


class ExportRequest(BaseModel):
    """Payload for selecting export format."""

    export_format: str = Field(..., description="Name of the exporter plugin (e.g. pdf, csv, json).")
