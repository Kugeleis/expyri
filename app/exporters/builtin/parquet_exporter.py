"""Parquet exporter plugin."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

from app.core.parquet import save_parquet_with_metadata
from app.exporters.base import Exporter, ExportResult, exporter_registry

if TYPE_CHECKING:
    from app.plots.base import PlotResult
    from app.stats.base import StatResult


@exporter_registry.register("parquet")
class ParquetExporter(Exporter):
    """Exporter that saves the preprocessed dataset and session metadata as a Parquet file."""

    @property
    def name(self) -> str:
        """Return the unique name of the exporter."""
        return "parquet"

    @property
    def content_type(self) -> str:
        """Return the default content type of the exporter."""
        return "application/octet-stream"

    def export(
        self,
        stat_results: list[StatResult],
        plots: list[PlotResult],
        df: pd.DataFrame,
        **kwargs: Any,
    ) -> ExportResult:
        """Export dataset and session metadata to Parquet format.

        Args:
            stat_results: The statistical test results (saved in metadata).
            plots: The list of plot results (saved in metadata).
            df: The dataset DataFrame.
            **kwargs: Extra parameters, expecting 'session'.

        Returns:
            An ExportResult containing the Parquet bytes.
        """
        session = kwargs.get("session")
        if session is None:
            raise ValueError("session keyword argument is required for ParquetExporter")

        # Create filename: <dataset>_<datetime>.parquet
        from datetime import UTC, datetime

        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        dataset_name = session.dataset_id or "dataset"
        filename = f"{dataset_name}_{timestamp}.parquet"

        # Save to exports dir on the server
        data_dir = Path(os.getenv("EXPYRI_DATA_DIR", "data")).resolve()
        export_dir = data_dir / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        parquet_path = export_dir / filename

        save_parquet_with_metadata(df, session, parquet_path)

        with open(parquet_path, "rb") as f:
            content_bytes = f.read()

        return ExportResult(
            content=content_bytes,
            content_type=self.content_type,
            filename=filename,
        )
