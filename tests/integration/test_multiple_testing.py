"""HTTP and HTMX results consistently present corrected significance."""

from collections.abc import Generator
from pathlib import Path

import pandas as pd
import pytest
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

from app.core.session import InMemorySessionStore, WizardSession
from app.datasets.repository import CsvDatasetRepository
from app.main import create_app
from app.stats.base import StatResult, stat_registry
from app.wizard.router.dependencies import get_dataset_repository


@pytest.fixture
def store() -> InMemorySessionStore:
    return InMemorySessionStore()


@pytest.fixture
def client(tmp_path: Path, store: InMemorySessionStore) -> Generator[TestClient, None, None]:
    pd.DataFrame(
        {
            "group": ["A"] * 5 + ["B"] * 5,
            "value": [1.0, 2.0, 3.0, 4.0, 5.0, 3.5, 4.5, 5.5, 6.5, 7.5],
            "value2": [1.0, 2.0, 3.0, 4.0, 5.0, 4.5, 5.5, 6.5, 7.5, 8.5],
        }
    ).to_csv(tmp_path / "normal.csv", index=False)
    application = create_app()
    application.dependency_overrides[get_dataset_repository] = lambda: CsvDatasetRepository(tmp_path)
    with TestClient(application) as test_client:
        application.state.session_store = store
        yield test_client


@pytest.fixture
def session(client: TestClient, store: InMemorySessionStore) -> WizardSession:
    session = WizardSession(
        dataset_id="normal", group_column="group", selected_value_columns=["value", "value2"], current_step="results"
    )
    session.stat_results = [
        StatResult(
            column_name=column,
            method_name="ttest_ind",
            test_statistic=2.0,
            p_value=raw,
            p_value_adjusted=adjusted,
            correction_method="holm",
            summary="Result",
        ).model_dump()
        for column, raw, adjusted in [("value", 0.03, 0.06), ("value2", 0.009, 0.027)]
    ]
    store.save(session)
    return session


@pytest.mark.parametrize("htmx", [False, True])
def test_results_show_raw_and_adjusted_values_with_adjusted_highlighting(
    client: TestClient, session: WizardSession, htmx: bool
) -> None:
    response = client.post(
        f"/wizard/sessions/{session.session_id}/update-sig-limit",
        data={"plots_sig_filter": "0.05"},
        headers={"HX-Request": "true"} if htmx else {},
    )
    assert response.status_code == 200
    soup = BeautifulSoup(response.text, "html.parser")
    headings = [heading.get_text(strip=True) for heading in soup.select(".results-table th")]
    assert "Raw p-value" in headings
    assert "Adjusted p-value" in headings
    rows = {row.select_one("td").get_text(strip=True): row for row in soup.select(".results-table tbody tr")}
    assert "result-row-significant" not in rows["value"].get("class", [])
    assert "result-row-strict" not in rows["value"].get("class", [])
    assert "0.030000" in rows["value"].get_text()
    assert "0.060000" in rows["value"].get_text()
    assert "result-row-significant" in rows["value2"].get("class", [])
    assert "result-row-strict" not in rows["value2"].get("class", [])
    assert "Holm" in soup.select_one("#multiple-testing-legend").get_text()
    assert "separately" in soup.select_one("#multiple-testing-legend").get_text()
    assert "Matches 1 variables" in soup.select_one("#filtered-plots-counter").get_text()
    assert "adjusted p-value" in soup.select_one("label[for='plots-sig-filter']").get_text().lower()


def test_adjusted_heading_sorts_without_mutating_session(client: TestClient, session: WizardSession) -> None:
    original = [dict(result) for result in session.stat_results]
    response = client.post(
        f"/wizard/sessions/{session.session_id}/update-sort?field=p_value_adjusted", headers={"HX-Request": "true"}
    )
    assert response.status_code == 200
    assert response.cookies["sort_field"] == "p_value_adjusted"
    soup = BeautifulSoup(response.text, "html.parser")
    assert [cell.get_text(strip=True) for cell in soup.select("tbody tr td:first-child")] == ["value2", "value"]
    assert session.stat_results == original


@pytest.mark.parametrize("legacy", [False, True])
def test_uncorrected_results_retain_raw_significance_and_show_no_adjustment(
    client: TestClient, session: WizardSession, legacy: bool
) -> None:
    for result in session.stat_results:
        result["p_value_adjusted"] = None
        result["correction_method"] = None
        if legacy:
            result.pop("p_value_adjusted")
            result.pop("correction_method")
    response = client.post(f"/wizard/sessions/{session.session_id}/update-sig-limit", data={"plots_sig_filter": "0.05"})
    assert response.status_code == 200
    soup = BeautifulSoup(response.text, "html.parser")
    rows = soup.select(".results-table tbody tr")
    assert "result-row-significant" in rows[0].get("class", [])
    assert "result-row-strict" in rows[1].get("class", [])
    assert "N/A" in rows[0].get_text()
    assert soup.select_one("#multiple-testing-legend") is None
    assert "Matches 2 variables" in soup.select_one("#filtered-plots-counter").get_text()


def test_plot_preview_identifies_adjusted_significance(client: TestClient, session: WizardSession) -> None:
    session.current_step = "plot_selection"
    session.plot_results = [{"column_name": "value2", "plot_type": "boxplot", "image_base64": ""}]
    response = client.post(f"/wizard/sessions/{session.session_id}/update-sig-limit", data={"plots_sig_filter": "0.05"})
    assert response.status_code == 200
    soup = BeautifulSoup(response.text, "html.parser")
    assert "adjusted p-value" in soup.select_one("#plots-generation-counter").get_text()
    assert "0.009000" in soup.select_one(".plot-result-meta").get_text()
    assert "Adjusted p: 0.027000" in soup.select_one(".plot-result-meta").get_text()


def test_select_dataset_without_previous_results_renders(client: TestClient) -> None:
    session_id = client.post("/wizard/sessions").json()["session_id"]
    response = client.post(f"/wizard/sessions/{session_id}/select-dataset-id", data={"dataset_id": "normal"})
    assert response.status_code == 200
    assert "Step 1: Select Dataset" in response.text


def test_json_evaluation_returns_adjustments_from_real_methods(client: TestClient, session: WizardSession) -> None:
    response = client.post(f"/wizard/sessions/{session.session_id}/method", json={"selected_method": "ttest_ind"})
    assert response.status_code == 200
    response = client.get(f"/wizard/sessions/{session.session_id}/results")
    assert response.status_code == 200
    results = {result["column_name"]: result for result in response.json()}
    raw = [
        stat_registry.get("ttest_ind").run({"A": [1, 2, 3, 4, 5], "B": values}).p_value
        for values in [[3.5, 4.5, 5.5, 6.5, 7.5], [4.5, 5.5, 6.5, 7.5, 8.5]]
    ]
    assert results["value"]["p_value"] == pytest.approx(raw[0])
    assert results["value2"]["p_value"] == pytest.approx(raw[1])
    assert results["value"]["p_value_adjusted"] == pytest.approx(max(raw[0], 2 * raw[1]))
    assert results["value2"]["p_value_adjusted"] == pytest.approx(2 * raw[1])
    assert all(result["correction_method"] == "holm" for result in results.values())
