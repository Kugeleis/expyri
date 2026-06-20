"""Dataset repository protocol and implementations.

The ``DatasetRepository`` protocol defines the interface for loading datasets.
Concrete implementations handle the actual I/O (CSV files, databases, etc.).
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

import pandas as pd

from app.datasets.models import ColumnInfo, DatasetInfo


class DatasetRepository(Protocol):
    """Protocol for dataset loading and introspection."""

    def list_datasets(self) -> list[DatasetInfo]:
        """List all available datasets."""
        ...  # pragma: no cover

    def load_dataset(self, dataset_id: str) -> pd.DataFrame:
        """Load a dataset by its ID.

        Raises:
            KeyError: If the dataset is not found.
        """
        ...  # pragma: no cover

    def get_schema(self, dataset_id: str) -> DatasetInfo:
        """Return schema metadata for a dataset.

        Raises:
            KeyError: If the dataset is not found.
        """
        ...  # pragma: no cover


class CsvDatasetRepository:
    """Loads datasets from CSV files in a configured directory.

    Each ``.csv`` file in the directory becomes a dataset.
    The dataset ID is the file stem (filename without extension).
    """

    def __init__(self, data_dir: Path) -> None:
        """Initialize with the directory containing CSV files.

        Args:
            data_dir: Path to the directory with CSV files.
        """
        self._data_dir = data_dir

    def _csv_path(self, dataset_id: str) -> Path:
        """Return the path for a dataset ID, raising KeyError if missing."""
        path = self._data_dir / f"{dataset_id}.csv"
        if not path.exists():
            msg = f"Dataset {dataset_id!r} not found at {path}"
            raise KeyError(msg)
        return path

    def list_datasets(self) -> list[DatasetInfo]:
        """List all CSV datasets in the configured directory."""
        datasets: list[DatasetInfo] = []
        if not self._data_dir.exists():
            return datasets
        for csv_file in sorted(self._data_dir.glob("*.csv")):
            datasets.append(
                DatasetInfo(
                    id=csv_file.stem,
                    name=csv_file.stem.replace("_", " ").title(),
                    description=f"CSV dataset from {csv_file.name}",
                )
            )
        return datasets

    def load_dataset(self, dataset_id: str) -> pd.DataFrame:
        """Load a CSV dataset by ID.

        Raises:
            KeyError: If the CSV file does not exist.
        """
        path = self._csv_path(dataset_id)
        return pd.read_csv(path)

    def get_schema(self, dataset_id: str) -> DatasetInfo:
        """Return column schema for a CSV dataset.

        Loads the first 0 rows to inspect dtypes without reading the full file.

        Raises:
            KeyError: If the CSV file does not exist.
        """
        path = self._csv_path(dataset_id)
        df = pd.read_csv(path, nrows=0)
        columns = [
            ColumnInfo(
                name=str(col),
                dtype=str(df[col].dtype),
                nullable=True,
            )
            for col in df.columns
        ]
        return DatasetInfo(
            id=dataset_id,
            name=dataset_id.replace("_", " ").title(),
            description=f"CSV dataset from {path.name}",
            columns=columns,
        )
