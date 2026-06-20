"""Unit tests for the filter system and builtin filters."""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from app.filters.base import apply_filter_pipeline, filter_registry
from app.filters.builtin.category_filter import CategoryFilter
from app.filters.builtin.numeric_range import NumericRangeFilter


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """Return a sample DataFrame for testing filters."""
    return pd.DataFrame(
        {
            "age": [20, 25, 30, 35, 40],
            "name": ["Alice", "Bob", "Charlie", "David", "Eve"],
            "city": ["New York", "Boston", "New York", "Boston", "Chicago"],
            "score": [1.5, 2.5, 3.5, 4.5, 5.5],
        }
    )


def test_registrations() -> None:
    """Verify built-in filters are correctly registered."""
    # Ensure they are eagerly imported and registered
    numeric_range = filter_registry.get("numeric_range")
    category = filter_registry.get("category_filter")

    assert isinstance(numeric_range, NumericRangeFilter)
    assert isinstance(category, CategoryFilter)


def test_numeric_range_properties() -> None:
    """Test properties of NumericRangeFilter."""
    filt = NumericRangeFilter()
    assert filt.name == "numeric_range"
    assert "numeric column" in filt.description


@pytest.mark.parametrize(
    ("params", "expected_len", "query_func"),
    [
        ({"column": "age", "min": 25}, 4, lambda df: df["age"].min() == 25),
        ({"column": "age", "max": 35}, 4, lambda df: df["age"].max() == 35),
        (
            {"column": "age", "min": 25, "max": 35},
            3,
            lambda df: list(df["age"]) == [25, 30, 35],
        ),
        (
            {"column": "score", "min": 2.0, "max": 5.0},
            3,
            lambda df: list(df["score"]) == [2.5, 3.5, 4.5],
        ),
    ],
)
def test_numeric_range_apply_valid(
    sample_df: pd.DataFrame,
    params: dict[str, Any],
    expected_len: int,
    query_func: Any,
) -> None:
    """Test valid applications of NumericRangeFilter."""
    filt = NumericRangeFilter()
    filt.validate_params(params)
    res = filt.apply(sample_df, params)
    assert len(res) == expected_len
    assert query_func(res)


@pytest.mark.parametrize(
    "params",
    [
        # Missing column
        {"min": 10},
        # Column not string
        {"column": 123, "min": 10},
        # Neither min nor max
        {"column": "age"},
        {"column": "age", "min": None, "max": None},
        # Min is not numeric
        {"column": "age", "min": "twenty"},
        # Max is not numeric
        {"column": "age", "max": "thirty"},
        # Min > Max
        {"column": "age", "min": 30, "max": 20},
    ],
)
def test_numeric_range_validate_invalid(params: dict[str, Any]) -> None:
    """Test parameter validation of NumericRangeFilter with invalid inputs."""
    filt = NumericRangeFilter()
    with pytest.raises(ValueError):  # noqa: PT011
        filt.validate_params(params)


def test_numeric_range_apply_errors(sample_df: pd.DataFrame) -> None:
    """Test error handling during apply in NumericRangeFilter."""
    filt = NumericRangeFilter()

    # Missing column in df
    with pytest.raises(ValueError, match="not found"):
        filt.apply(sample_df, {"column": "nonexistent", "min": 10})

    # Non-numeric column in df
    with pytest.raises(ValueError, match="must be numeric"):
        filt.apply(sample_df, {"column": "name", "min": 10})


def test_category_filter_properties() -> None:
    """Test properties of CategoryFilter."""
    filt = CategoryFilter()
    assert filt.name == "category_filter"
    assert "categorical" in filt.description


@pytest.mark.parametrize(
    ("params", "expected_len", "expected_names"),
    [
        (
            {"column": "city", "values": ["Boston", "Chicago"], "mode": "include"},
            3,
            ["Bob", "David", "Eve"],
        ),
        (
            {"column": "city", "values": ["Boston", "Chicago"], "mode": "exclude"},
            2,
            ["Alice", "Charlie"],
        ),
        (
            {"column": "name", "values": ["Alice"]},
            1,
            ["Alice"],
        ),  # Default mode: include
    ],
)
def test_category_filter_apply_valid(
    sample_df: pd.DataFrame,
    params: dict[str, Any],
    expected_len: int,
    expected_names: list[str],
) -> None:
    """Test valid applications of CategoryFilter."""
    filt = CategoryFilter()
    filt.validate_params(params)
    res = filt.apply(sample_df, params)
    assert len(res) == expected_len
    assert list(res["name"]) == expected_names


@pytest.mark.parametrize(
    "params",
    [
        # Missing column
        {"values": ["Boston"]},
        # Column not string
        {"column": 123, "values": ["Boston"]},
        # Missing values
        {"column": "city"},
        # Values not list
        {"column": "city", "values": "Boston"},
        # Invalid mode
        {"column": "city", "values": ["Boston"], "mode": "invalid"},
    ],
)
def test_category_filter_validate_invalid(params: dict[str, Any]) -> None:
    """Test parameter validation of CategoryFilter with invalid inputs."""
    filt = CategoryFilter()
    with pytest.raises(ValueError):  # noqa: PT011
        filt.validate_params(params)


def test_category_filter_apply_errors(sample_df: pd.DataFrame) -> None:
    """Test error handling during apply in CategoryFilter."""
    filt = CategoryFilter()

    # Missing column in df
    with pytest.raises(ValueError, match="not found"):
        filt.apply(sample_df, {"column": "nonexistent", "values": ["A"]})


def test_pipeline_valid(sample_df: pd.DataFrame) -> None:
    """Test apply_filter_pipeline with valid configs."""
    configs = [
        {"name": "numeric_range", "params": {"column": "age", "min": 25}},
        {"name": "category_filter", "params": {"column": "city", "values": ["Boston"]}},
    ]
    res = apply_filter_pipeline(sample_df, configs)
    # original df should not be mutated
    assert len(sample_df) == 5

    # expected: age >= 25 -> Bob, Charlie, David, Eve (Boston, NY, Boston, Chicago)
    # city in Boston -> Bob, David
    assert len(res) == 2
    assert list(res["name"]) == ["Bob", "David"]


@pytest.mark.parametrize(
    ("configs", "match_str"),
    [
        ([{"params": {"column": "age"}}], "contain a 'name' field"),
        ([{"name": "numeric_range", "params": "invalid"}], "must be a dictionary"),
    ],
)
def test_pipeline_errors(
    sample_df: pd.DataFrame, configs: list[dict[str, Any]], match_str: str
) -> None:
    """Test error handling in apply_filter_pipeline."""
    with pytest.raises(ValueError, match=match_str):
        apply_filter_pipeline(sample_df, configs)
