"""Unit tests for the dataset repository."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.datasets.models import DatasetInfo
from app.datasets.repository import CsvDatasetRepository


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Create a temp directory with a sample CSV."""
    csv_content = "group,value\nA,1.0\nA,2.0\nB,3.0\nB,4.0\n"
    (tmp_path / "sample.csv").write_text(csv_content)
    return tmp_path


@pytest.fixture
def repo(data_dir: Path) -> CsvDatasetRepository:
    """Provide a CsvDatasetRepository pointing at the temp dir."""
    return CsvDatasetRepository(data_dir)


def test_list_datasets(repo: CsvDatasetRepository) -> None:
    """list_datasets returns metadata for each CSV file."""
    datasets = repo.list_datasets()
    assert len(datasets) == 1
    assert datasets[0].id == "sample"
    assert isinstance(datasets[0], DatasetInfo)


def test_list_datasets_empty_dir(tmp_path: Path) -> None:
    """list_datasets returns empty list for directory with no CSVs."""
    repo = CsvDatasetRepository(tmp_path)
    assert repo.list_datasets() == []


def test_list_datasets_missing_dir(tmp_path: Path) -> None:
    """list_datasets returns empty list for non-existent directory."""
    repo = CsvDatasetRepository(tmp_path / "nonexistent")
    assert repo.list_datasets() == []


def test_load_dataset(repo: CsvDatasetRepository) -> None:
    """load_dataset returns a DataFrame with expected shape."""
    df = repo.load_dataset("sample")
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["group", "value"]
    assert len(df) == 4


def test_load_dataset_missing_raises(repo: CsvDatasetRepository) -> None:
    """load_dataset raises KeyError for missing dataset."""
    with pytest.raises(KeyError, match="not found"):
        repo.load_dataset("nonexistent")


def test_get_schema(repo: CsvDatasetRepository) -> None:
    """get_schema returns column metadata."""
    schema = repo.get_schema("sample")
    assert schema.id == "sample"
    assert len(schema.columns) == 2
    assert schema.columns[0].name == "group"
    assert schema.columns[1].name == "value"


def test_get_schema_missing_raises(repo: CsvDatasetRepository) -> None:
    """get_schema raises KeyError for missing dataset."""
    with pytest.raises(KeyError, match="not found"):
        repo.get_schema("nonexistent")
