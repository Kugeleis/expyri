from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def sync_client() -> TestClient:
    """Provide a synchronous TestClient."""
    return TestClient(app)


def test_hierarchical_wizard_flow_e2e(sync_client: TestClient, hierarchical_df: Any) -> None:
    """Verify the full end-to-end wizard flow using hierarchical data."""
    # 1. Generate hierarchical test data and upload it
    df = hierarchical_df(n_groups=2, n_clusters=4, n_units=10)
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    files = {"file": ("hierarchical_data.csv", csv_bytes, "text/csv")}

    resp = sync_client.post("/wizard/upload", files=files)
    assert resp.status_code == 200
    dataset_info = resp.json()
    dataset_id = dataset_info["id"]

    # 2. Create session
    resp = sync_client.post("/wizard/sessions")
    assert resp.status_code == 200
    session_data = resp.json()
    session_id = session_data["session_id"]

    # 3. Select dataset and map columns
    resp = sync_client.post(
        f"/wizard/sessions/{session_id}/dataset",
        json={
            "dataset_id": dataset_id,
            "group_column": "group",
            "selected_value_columns": ["metric"],
            "selected_discrete_columns": [],
            "selected_groups": ["Group_A", "Group_B"],
        },
    )
    assert resp.status_code == 200

    # 4. Set HierarchyConfig
    resp = sync_client.post(
        f"/wizard/sessions/{session_id}/hierarchy",
        json={"group_col": "group", "cluster_col": "cluster", "unit_col": "unit", "x_col": "x", "y_col": "y"},
    )
    assert resp.status_code == 200
    hierarchy_info = resp.json()
    assert "metric_kinds" in hierarchy_info
    assert hierarchy_info["metric_kinds"]["metric"] == "continuous"
    assert hierarchy_info["session"]["hierarchy"]["group_col"] == "group"

    # 5. Configure and apply preprocessing filters (including cluster_exclusion)
    resp = sync_client.post(
        f"/wizard/sessions/{session_id}/filters",
        json={
            "filters_config": [
                {
                    "name": "cluster_exclusion",
                    "params": {"exclusions": [{"cluster_id": "Cluster_0", "reason": "outlier"}]},
                }
            ]
        },
    )
    assert resp.status_code == 200
    session_after_filt = resp.json()
    assert len(session_after_filt["excluded_clusters"]) == 1
    assert session_after_filt["excluded_clusters"][0]["cluster_id"] == "Cluster_0"

    # 6. List applicable methods
    resp = sync_client.get(f"/wizard/sessions/{session_id}/methods")
    assert resp.status_code == 200
    methods = resp.json()
    method_names = [m["name"] for m in methods]
    # Under hierarchical configuration, continuous plugins should be returned
    assert "cluster_mean_anova" in method_names or "linear_mixed_model" in method_names

    # 7. Select a statistical method
    resp = sync_client.post(
        f"/wizard/sessions/{session_id}/method",
        json={"selected_method": "cluster_mean_anova", "selected_discrete_method": None},
    )
    assert resp.status_code == 200

    # 8. Run statistical evaluation
    resp = sync_client.get(f"/wizard/sessions/{session_id}/results")
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 1
    assert results[0]["method_name"] == "cluster_mean_anova"
    assert results[0]["p_value"] >= 0.0

    # 9. List applicable plots
    resp = sync_client.get(f"/wizard/sessions/{session_id}/plots")
    assert resp.status_code == 200
    plots = resp.json()
    plot_names = [p["name"] for p in plots]
    assert "cluster_mean_bar_plot" in plot_names
    assert "cluster_spatial_heatmap" in plot_names

    # 10. Generate selected plots
    resp = sync_client.post(
        f"/wizard/sessions/{session_id}/plots",
        json={"selected_plots": ["cluster_mean_bar_plot", "cluster_spatial_heatmap"], "top_n_columns": 1},
    )
    assert resp.status_code == 200
    session_after_plots = resp.json()
    assert len(session_after_plots["plot_results"]) == 2

    # 11. Export
    resp = sync_client.post(f"/wizard/sessions/{session_id}/export", json={"export_format": "csv"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
