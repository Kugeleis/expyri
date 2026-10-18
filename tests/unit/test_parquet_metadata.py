import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import pytest
from fastapi.testclient import TestClient

from app.core.parquet import save_parquet_with_metadata
from app.core.session import ClusterExclusion, HierarchyConfig, WizardSession
from app.main import create_app


def test_save_parquet_with_metadata(tmp_path: Path) -> None:
    """Verify that save_parquet_with_metadata correctly serializes all ExPyRi settings into parquet metadata."""
    # 1. Create a dummy session with configuration
    session = WizardSession(
        session_id="test_session_123",
        dataset_id="test_dataset",
        group_column="group",
        selected_value_columns=["val1", "val2"],
        selected_discrete_columns=["cat1"],
        selected_groups=["A", "B"],
        filters_config=[{"type": "drop_nan"}],
        selected_method="t-test",
        selected_discrete_method="chi-square",
        stat_results=[{"column_name": "val1", "p_value": 0.01}],
        selected_plots=["boxplot"],
        plot_results=[{"plot_type": "boxplot"}],
        top_n_columns=2,
        hierarchy=HierarchyConfig(
            group_col="group",
            cluster_col="cluster",
            selected_clusters=["C1", "C2"],
        ),
        excluded_clusters=[ClusterExclusion(cluster_id="C3", reason="Outlier")],
    )

    # 2. Create dummy dataframe
    df = pd.DataFrame(
        {
            "group": ["A", "B", "A", "B"],
            "val1": [1.0, 2.0, 1.5, 2.5],
            "val2": [10, 20, 15, 25],
            "cat1": ["x", "y", "x", "y"],
            "cluster": ["C1", "C2", "C1", "C2"],
        }
    )

    parquet_file = tmp_path / "test.parquet"
    save_parquet_with_metadata(df, session, parquet_file)

    # 3. Read back with pyarrow
    assert parquet_file.exists()
    table = pq.read_table(parquet_file)
    df_read = table.to_pandas()
    assert len(df_read) == 4
    assert list(df_read.columns) == ["group", "val1", "val2", "cat1", "cluster"]

    # 4. Check metadata
    metadata = table.schema.metadata
    assert metadata is not None

    # decode JSON values
    dataset = json.loads(metadata[b"dataset"].decode("utf-8"))
    assert dataset == "test_dataset"

    timestamp_str = json.loads(metadata[b"timestamp"].decode("utf-8"))
    timestamp = datetime.fromisoformat(timestamp_str)
    assert (datetime.now(UTC) - timestamp).total_seconds() < 10

    methods = json.loads(metadata[b"selected_statistical_methods"].decode("utf-8"))
    assert methods["continuous"] == "t-test"
    assert methods["discrete"] == "chi-square"

    stat_results = json.loads(metadata[b"statistic_results"].decode("utf-8"))
    assert stat_results == [{"column_name": "val1", "p_value": 0.01}]

    plots_selected = json.loads(metadata[b"plots_selected"].decode("utf-8"))
    assert plots_selected == ["boxplot"]

    # Test complete reproducibility of choices/info
    group_column = json.loads(metadata[b"group_column"].decode("utf-8"))
    assert group_column == "group"

    filters_config = json.loads(metadata[b"filters_config"].decode("utf-8"))
    assert filters_config == [{"type": "drop_nan"}]

    hierarchy = json.loads(metadata[b"hierarchy"].decode("utf-8"))
    assert hierarchy["group_col"] == "group"
    assert hierarchy["cluster_col"] == "cluster"
    assert hierarchy["selected_clusters"] == ["C1", "C2"]

    excluded_clusters = json.loads(metadata[b"excluded_clusters"].decode("utf-8"))
    assert excluded_clusters == [{"cluster_id": "C3", "reason": "Outlier"}]


def test_parquet_export_route(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Verify that the GET endpoint /wizard/sessions/{session_id}/export?format=parquet
    triggers parquet save and returns the file download.
    """
    # Set up app
    app = create_app()

    with TestClient(app) as client:
        # Inject our session
        store = app.state.session_store
        session = store.create()
        session_id = session.session_id

        # Populate session choices so it passes the _export_guard
        session.current_step = "export"
        session.dataset_id = "ds_pq"
        session.group_column = "group"
        session.selected_value_columns = ["val"]
        session.selected_method = "t-test"
        session.stat_results = [
            {
                "column_name": "val",
                "method_name": "t-test",
                "test_statistic": 1.23,
                "p_value": 0.01,
                "p_value_adjusted": 0.03,
                "correction_method": "holm",
                "summary": "Summary",
            }
        ]
        session.selected_plots = ["boxplot"]
        session.plot_results = [{"plot_type": "boxplot", "column_name": "val", "image_base64": "dummy"}]

        # Set EXPYRI_DATA_DIR to tmp_path
        monkeypatch.setenv("EXPYRI_DATA_DIR", str(tmp_path))

        # Save a dummy dataset to tmp_path so it can be loaded
        df = pd.DataFrame({"group": ["A", "B"], "val": [1.0, 2.0]})
        df.to_csv(tmp_path / "ds_pq.csv", index=False)

        # Call the GET route
        resp = client.get(f"/wizard/sessions/{session_id}/export?format=parquet", follow_redirects=False)

    # It should return the file as a downloadable response
    assert resp.status_code == 200
    cd = resp.headers["Content-Disposition"]
    assert "attachment; filename=" in cd
    filename = cd.split("filename=")[1]
    assert filename.startswith("ds_pq_")
    assert filename.endswith(".parquet")

    # The parquet file should have been created in exports/
    parquet_path = tmp_path / "exports" / filename
    assert parquet_path.exists()

    # Read schema metadata from response content and check
    import io

    table = pq.read_table(io.BytesIO(resp.content))
    metadata = table.schema.metadata
    assert metadata is not None
    assert json.loads(metadata[b"dataset"].decode("utf-8")) == "ds_pq"
    assert json.loads(metadata[b"group_column"].decode("utf-8")) == "group"
    results = json.loads(metadata[b"statistic_results"].decode("utf-8"))
    assert results[0]["p_value"] == 0.01
    assert results[0]["p_value_adjusted"] == 0.03
    assert results[0]["correction_method"] == "holm"
