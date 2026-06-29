"""Integration tests for HTMX and HTML compatibility views in the wizard flow."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.datasets.repository import CsvDatasetRepository
from app.main import app
from app.wizard.router import get_dataset_repository


@pytest.fixture
def test_data_dir(tmp_path: Path) -> Path:
    """Create a temporary directory with test CSV files."""
    np.random.seed(42)
    # Balanced data with continuous, discrete, groups, clusters, unit, and coordinates
    df = pd.DataFrame(
        {
            "group": ["A"] * 10 + ["B"] * 10,
            "cluster": ["C1"] * 5 + ["C2"] * 5 + ["C3"] * 5 + ["C4"] * 5,
            "unit": [f"U{i}" for i in range(20)],
            "x": [float(i % 5) for i in range(20)],
            "y": [float(i // 5) for i in range(20)],
            "value": np.random.normal(loc=10.0, scale=1.0, size=20),
            "category": ["X", "Y"] * 10,
        }
    )
    df.to_csv(tmp_path / "htmx_data.csv", index=False)
    return tmp_path


@pytest.fixture
def client(test_data_dir: Path) -> Generator[TestClient, None, None]:
    """TestClient with overridden dataset repository dependency."""
    repo = CsvDatasetRepository(test_data_dir)
    app.dependency_overrides[get_dataset_repository] = lambda: repo
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_homepage_and_htmx_headers(client: TestClient) -> None:
    """Verify that root /wizard endpoints render full page or partials depending on headers."""
    # Full HTML Response
    resp = client.get("/wizard/")
    assert resp.status_code == 200
    assert "<!doctype html>" in resp.text.lower()
    assert "Experiment Evaluation Wizard" in resp.text

    # HTMX Partial Response
    resp_htmx = client.get("/wizard/", headers={"HX-Request": "true"})
    assert resp_htmx.status_code == 200
    assert "<!doctype html>" not in resp_htmx.text.lower()
    # Check that parts of partials are present
    assert "step-panel" in resp_htmx.text


def test_restart_session_htmx_variants(client: TestClient) -> None:
    """Verify restart_session handles HTMX, JSON and Redirect responses correctly."""
    resp = client.post("/wizard/sessions")
    session_id = resp.json()["session_id"]

    # 1. HTMX Request: Should redirect using HX-Redirect header
    resp_htmx = client.post(f"/wizard/sessions/{session_id}/restart", headers={"HX-Request": "true"})
    assert resp_htmx.status_code == 200
    assert resp_htmx.headers.get("HX-Redirect") == "/"

    # 2. JSON Request: Should return session JSON
    resp_json = client.post(f"/wizard/sessions/{session_id}/restart", headers={"Accept": "application/json"})
    assert resp_json.status_code == 200
    assert "session_id" in resp_json.json()

    # 3. Standard Request: Should return 303 Redirect
    resp_std = client.post(f"/wizard/sessions/{session_id}/restart", follow_redirects=False)
    assert resp_std.status_code == 303
    assert resp_std.headers.get("location") == "/"


def test_wizard_htmx_dataset_selection_flow(client: TestClient) -> None:
    """Test HTMX routes in Step 1: select dataset, toggle hierarchy, update group column, select columns."""
    resp = client.post("/wizard/sessions")
    session_id = resp.json()["session_id"]

    # Select dataset
    resp = client.post(
        f"/wizard/sessions/{session_id}/select-dataset-id",
        data={"dataset_id": "htmx_data"},
        headers={"HX-Request": "true"},
    )
    assert resp.status_code == 200
    assert "htmx_data" in resp.text

    # Toggle hierarchy true
    resp = client.post(
        f"/wizard/sessions/{session_id}/toggle-hierarchy",
        params={"enabled": "true"},
        headers={"HX-Request": "true"},
    )
    assert resp.status_code == 200

    # Toggle hierarchy false
    resp = client.post(
        f"/wizard/sessions/{session_id}/toggle-hierarchy",
        params={"enabled": "false"},
        headers={"HX-Request": "true"},
    )
    assert resp.status_code == 200

    # Update group column
    resp = client.post(
        f"/wizard/sessions/{session_id}/update-group-col",
        data={"group_column": "group"},
        headers={"HX-Request": "true"},
    )
    assert resp.status_code == 200

    # Submit dataset config
    resp = client.post(
        f"/wizard/sessions/{session_id}/submit-dataset-config",
        data={
            "group_column": "group",
            "selected_groups": ["A", "B"],
            "selected_value_columns": ["value"],
            "selected_discrete_columns": ["category"],
        },
        headers={"HX-Request": "true"},
    )
    assert resp.status_code == 200


def test_wizard_htmx_filters_flow(client: TestClient) -> None:
    """Test HTMX routes in Step 2: filters update fields, addition, and removal."""
    # Setup session at step 2
    resp = client.post("/wizard/sessions")
    session_id = resp.json()["session_id"]
    client.post(f"/wizard/sessions/{session_id}/select-dataset-id", data={"dataset_id": "htmx_data"})
    client.post(
        f"/wizard/sessions/{session_id}/submit-dataset-config",
        data={
            "group_column": "group",
            "selected_groups": ["A", "B"],
            "selected_value_columns": ["value"],
            "selected_discrete_columns": ["category"],
        },
    )

    # Update filter fields for category filter
    resp = client.post(f"/wizard/sessions/{session_id}/update-filter-fields", data={"filter_type": "category_filter"})
    assert resp.status_code == 200
    assert "category" in resp.text or "values" in resp.text

    # Update filter fields for cluster exclusion
    resp = client.post(f"/wizard/sessions/{session_id}/update-filter-fields", data={"filter_type": "cluster_exclusion"})
    assert resp.status_code == 200
    assert "reason" in resp.text

    # Add numeric range filter
    resp = client.post(
        f"/wizard/sessions/{session_id}/add-filter",
        data={"filter_type": "numeric_range", "column": "value", "min_val": "5.0", "max_val": "15.0"},
        headers={"HX-Request": "true"},
    )
    assert resp.status_code == 200
    assert "numeric_range" in resp.text

    # Remove filter via DELETE
    resp = client.delete(
        f"/wizard/sessions/{session_id}/filters/0",
        headers={"HX-Request": "true"},
    )
    assert resp.status_code == 200
    assert "no-filters-msg" in resp.text


def test_wizard_htmx_method_results_plots_export(client: TestClient) -> None:
    """Test HTMX routes in Step 3-6: method updates, running stats, selecting plots, exporting report."""
    resp = client.post("/wizard/sessions")
    session_id = resp.json()["session_id"]
    client.post(f"/wizard/sessions/{session_id}/select-dataset-id", data={"dataset_id": "htmx_data"})
    client.post(
        f"/wizard/sessions/{session_id}/submit-dataset-config",
        data={
            "group_column": "group",
            "selected_groups": ["A", "B"],
            "selected_value_columns": ["value"],
            "selected_discrete_columns": ["category"],
        },
    )

    # Submit filters to get to STAT_METHOD step
    client.post(f"/wizard/sessions/{session_id}/submit-filters")

    # Update method
    resp = client.post(
        f"/wizard/sessions/{session_id}/update-method",
        data={"selected_method": "ttest_ind", "selected_discrete_method": "chi_square"},
        headers={"HX-Request": "true"},
    )
    assert resp.status_code == 200

    # Submit method (runs tests and transitions to Step 4: results)
    resp = client.post(
        f"/wizard/sessions/{session_id}/submit-method",
        data={"selected_method": "ttest_ind", "selected_discrete_method": "chi_square"},
        headers={"HX-Request": "true"},
    )
    assert resp.status_code == 200
    assert "results" in resp.text

    # Update sort on results
    resp = client.post(
        f"/wizard/sessions/{session_id}/update-sort",
        params={"field": "column_name"},
        headers={"HX-Request": "true"},
    )
    assert resp.status_code == 200

    # Update sig limit
    resp = client.post(
        f"/wizard/sessions/{session_id}/update-sig-limit",
        data={"plots_sig_filter": 0.05},
        headers={"HX-Request": "true"},
    )
    assert resp.status_code == 200

    # Submit results (transitions to Step 5: plots)
    resp = client.post(
        f"/wizard/sessions/{session_id}/submit-results",
        headers={"HX-Request": "true"},
    )
    assert resp.status_code == 200
    assert "plot_selection" in resp.text

    # Generate plots
    resp = client.post(
        f"/wizard/sessions/{session_id}/generate-plots",
        data={"selected_plots": ["boxplot"]},
        headers={"HX-Request": "true"},
    )
    assert resp.status_code == 200

    # Submit plots (transitions to Step 6: export)
    resp = client.post(
        f"/wizard/sessions/{session_id}/submit-plots",
        headers={"HX-Request": "true"},
    )
    assert resp.status_code == 200
    assert "export" in resp.text

    # Submit export (downloads report) - JSON route /sessions/{session_id}/export
    resp = client.post(
        f"/wizard/sessions/{session_id}/export",
        json={"export_format": "csv"},
    )
    assert resp.status_code == 200
    assert "text/csv" in resp.headers.get("content-type", "")


def test_compatibility_and_navigation_routes(client: TestClient) -> None:
    """Test compatibility routes and standard HTTP step navigation."""
    resp = client.post("/wizard/sessions")
    session_id = resp.json()["session_id"]
    client.post(f"/wizard/sessions/{session_id}/select-dataset-id", data={"dataset_id": "htmx_data"})
    client.post(
        f"/wizard/sessions/{session_id}/submit-dataset-config",
        data={
            "group_column": "group",
            "selected_groups": ["A", "B"],
            "selected_value_columns": ["value"],
            "selected_discrete_columns": ["category"],
        },
    )

    # Navigating back using compatibility route POST
    resp = client.post(
        f"/wizard/sessions/{session_id}/go-to/dataset_selection",
        headers={"HX-Request": "true"},
    )
    assert resp.status_code == 200
    assert "dataset_selection" in resp.text

    # Navigate back/forward via navigation route
    resp = client.post(
        f"/wizard/sessions/{session_id}/navigate",
        params={"direction": "forward"},
        headers={"HX-Request": "true"},
    )
    assert resp.status_code == 200

    resp = client.post(
        f"/wizard/sessions/{session_id}/navigate",
        params={"direction": "back"},
        headers={"HX-Request": "true"},
    )
    assert resp.status_code == 200

    # Post with unknown step should raise 400
    resp_err = client.post(f"/wizard/sessions/{session_id}/go-to/unknown_step")
    assert resp_err.status_code == 400
