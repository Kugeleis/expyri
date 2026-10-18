"""Wizard labels are presentation metadata, never persisted method identifiers."""

from collections.abc import Generator
from pathlib import Path

import pandas as pd
import pytest
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

from app.core.session import HierarchyConfig, InMemorySessionStore, WizardSession
from app.datasets.repository import CsvDatasetRepository
from app.main import create_app
from app.plots.base import PlotResult
from app.stats.base import DataProperties, StatMethod, StatResult, stat_registry
from app.wizard.router.dependencies import get_dataset_repository


class LegacyCustom(StatMethod):
    name = "legacy_custom"
    description = "A custom plugin with no display-name override."

    def is_applicable(self, properties: DataProperties) -> bool:
        return True

    def run(self, groups: dict[str, list[float]]) -> StatResult:
        return StatResult(method_name=self.name, test_statistic=1.0, p_value=0.5, summary="Custom result")


class LabelledCustom(LegacyCustom):
    @property
    def display_name(self) -> str:
        return "Custom <em>label</em> & notes"


@pytest.fixture(autouse=True)
def temporary_methods(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(stat_registry, "_plugins", stat_registry.list_all())
    stat_registry.register("legacy_alias")(LegacyCustom)
    stat_registry.register("labelled_alias")(LabelledCustom)


@pytest.fixture
def store() -> InMemorySessionStore:
    return InMemorySessionStore()


@pytest.fixture
def client(tmp_path: Path, store: InMemorySessionStore) -> Generator[TestClient, None, None]:
    pd.DataFrame(
        {
            "group": ["A"] * 5 + ["B"] * 5,
            "cluster": ["C1", "C1", "C2", "C2", "C2", "C3", "C3", "C4", "C4", "C4"],
            "value": [10.0, 10.5, 11.0, 10.2, 9.8, 12.0, 12.5, 13.0, 12.2, 11.8],
            "category": ["X", "Y"] * 5,
        }
    ).to_csv(tmp_path / "normal.csv", index=False)
    repo = CsvDatasetRepository(tmp_path)
    application = create_app()
    application.dependency_overrides[get_dataset_repository] = lambda: repo
    with TestClient(application) as test_client:
        application.state.session_store = store
        yield test_client


@pytest.fixture
def session(client: TestClient, store: InMemorySessionStore) -> WizardSession:
    session = store.create()
    session.dataset_id = "normal"
    session.group_column = "group"
    session.selected_groups = ["A", "B"]
    session.selected_value_columns = ["value"]
    session.selected_discrete_columns = ["category"]
    session.current_step = "stat_method"
    return session


@pytest.mark.parametrize("htmx", [False, True])
@pytest.mark.parametrize("step", ["stat_method", "results", "plot_selection"])
@pytest.mark.parametrize(
    ("method_id", "label"),
    [
        ("ttest_ind", "Independent two-sample t-test"),
        ("mann_whitney", "Mann-Whitney U test"),
        ("anova", "One-way ANOVA"),
        ("kruskal_wallis", "Kruskal-Wallis H test"),
        ("chi_square", "Chi-square test of independence"),
        ("cluster_mean_anova", "One-way ANOVA on cluster means"),
        ("cluster_mean_kruskal_wallis", "Kruskal-Wallis H test on cluster means"),
        ("proportion_kruskal_wallis", "Kruskal-Wallis H test on corrected cluster proportions"),
        ("linear_mixed_model", "Linear mixed-effects model (LMM)"),
        ("grubbs_cluster_outlier", "Grubbs outlier test on cluster means"),
        ("levene_cluster_uniformity", "Levene's test of within-cluster spread"),
    ],
)
def test_builtin_labels_across_wizard(
    client: TestClient, session: WizardSession, method_id: str, label: str, step: str, htmx: bool
) -> None:
    session.hierarchy = HierarchyConfig(group_col="group", cluster_col="cluster")
    session.stat_results = [
        StatResult(
            column_name="value", method_name=method_id, test_statistic=1.0, p_value=0.01, summary="Result"
        ).model_dump()
    ]
    session.plot_results = [PlotResult(column_name="value", plot_type="boxplot", image_base64="").model_dump()]
    session.current_step = step
    headers = {"HX-Request": "true"} if htmx else {}
    response = client.post(
        f"/wizard/sessions/{session.session_id}/update-sig-limit", data={"plots_sig_filter": "0.05"}, headers=headers
    )
    assert response.status_code == 200
    assert ("<!doctype html>" in response.text.lower()) is not htmx
    soup = BeautifulSoup(response.text, "html.parser")
    if step == "stat_method":
        radio = soup.select_one(f"input[value='{method_id}']")
        assert radio is not None
        assert radio.find_parent("label").strong.get_text(strip=True) == label
        assert "GMM" not in response.text
        assert "Linear mixed-effects model (LMM)" in response.text
    elif step == "results":
        assert soup.select_one(".results-table tbody tr td:nth-of-type(2)").get_text(strip=True) == label
    else:
        assert soup.select_one(".plot-result-meta span").get_text(strip=True) == f"Method: {label}"


@pytest.mark.parametrize("htmx", [False, True])
@pytest.mark.parametrize("step", ["stat_method", "results", "plot_selection"])
@pytest.mark.parametrize(
    ("method_id", "label"),
    [("legacy_alias", "Legacy Custom"), ("labelled_alias", "Custom <em>label</em> & notes")],
)
def test_custom_labels_use_registry_keys_and_remain_escaped(
    client: TestClient, session: WizardSession, method_id: str, label: str, step: str, htmx: bool
) -> None:
    session.selected_method = method_id
    session.stat_results = [
        StatResult(
            column_name="value", method_name=method_id, test_statistic=1.0, p_value=0.01, summary="Result"
        ).model_dump()
    ]
    session.plot_results = [PlotResult(column_name="value", plot_type="boxplot", image_base64="").model_dump()]
    session.current_step = step
    original_results = [dict(result) for result in session.stat_results]
    response = client.post(
        f"/wizard/sessions/{session.session_id}/update-sig-limit",
        data={"plots_sig_filter": "0.05"},
        headers={"HX-Request": "true"} if htmx else {},
    )
    assert response.status_code == 200
    soup = BeautifulSoup(response.text, "html.parser")
    if step == "stat_method":
        radio = soup.select_one(f"input[value='{method_id}']")
        assert radio is not None and radio.has_attr("checked") and not radio.has_attr("disabled")
        label_element = radio.find_parent("label").strong
    elif step == "results":
        label_element = soup.select_one(".results-table tbody tr td:nth-of-type(2)")
    else:
        label_element = soup.select_one(".plot-result-meta span")
    assert label_element.get_text(strip=True) == (f"Method: {label}" if step == "plot_selection" else label)
    assert label_element.find("em") is None
    assert session.stat_results == original_results
    assert session.selected_method == method_id


@pytest.mark.parametrize("htmx", [False, True])
@pytest.mark.parametrize("step", ["results", "plot_selection"])
def test_unknown_result_labels_are_escaped_without_rewriting_or_reordering_results(
    client: TestClient, session: WizardSession, step: str, htmx: bool
) -> None:
    unknown_id = "historical_<em>method</em>&old"
    session.stat_results = [
        StatResult(
            column_name=column, method_name=method_id, test_statistic=1.5, p_value=0.02, summary="Original result"
        ).model_dump()
        for column, method_id in [("value", unknown_id), ("category", "ttest_ind")]
    ]
    session.plot_results = [PlotResult(column_name="value", plot_type="boxplot", image_base64="").model_dump()]
    session.current_step = step
    original_results = [dict(result) for result in session.stat_results]
    response = client.post(
        f"/wizard/sessions/{session.session_id}/update-sort?field=method_name",
        headers={"HX-Request": "true"} if htmx else {},
    )
    assert response.status_code == 200
    soup = BeautifulSoup(response.text, "html.parser")
    if step == "results":
        labels = [cell.get_text(strip=True) for cell in soup.select(".results-table tbody tr td:nth-of-type(2)")]
        assert labels == [unknown_id, "Independent two-sample t-test"]
    else:
        assert soup.select_one(".plot-result-meta span").get_text(strip=True) == f"Method: {unknown_id}"
    assert soup.find("em") is None
    assert session.stat_results == original_results


@pytest.mark.parametrize("htmx", [False, True])
def test_http_flow_keeps_machine_ids_in_forms_sessions_and_api_export_payloads(
    client: TestClient, session: WizardSession, htmx: bool
) -> None:
    prefix = f"/wizard/sessions/{session.session_id}"
    headers = {"HX-Request": "true"} if htmx else {}
    methods_response = client.get(f"{prefix}/methods")
    assert methods_response.status_code == 200
    ttest = next(method for method in methods_response.json() if method["name"] == "ttest_ind")
    assert set(ttest) == {"name", "description", "variable_type"}
    selection = client.post(
        f"{prefix}/update-method",
        data={"selected_method": "ttest_ind", "selected_discrete_method": "chi_square"},
        headers=headers,
    )
    assert selection.status_code == 200
    soup = BeautifulSoup(selection.text, "html.parser")
    for method_id in ("ttest_ind", "chi_square"):
        radio = soup.select_one(f"input[value='{method_id}']")
        assert radio.has_attr("checked") and not radio.has_attr("disabled")
    lmm = soup.select_one("input[value='linear_mixed_model']")
    assert lmm.has_attr("disabled")
    continuous = soup.select("input[name='selected_method']")
    states = [radio.has_attr("disabled") for radio in continuous]
    assert states == sorted(states)

    results = client.post(
        f"{prefix}/submit-method",
        data={"selected_method": "ttest_ind", "selected_discrete_method": "chi_square"},
        headers=headers,
    )
    assert results.status_code == 200
    soup = BeautifulSoup(results.text, "html.parser")
    labels = [cell.get_text(strip=True) for cell in soup.select(".results-table tbody tr td:nth-of-type(2)")]
    assert labels == ["Chi-square test of independence", "Independent two-sample t-test"]
    assert {result["method_name"] for result in session.stat_results} == {"ttest_ind", "chi_square"}
    original_results = [dict(result) for result in session.stat_results]
    assert client.post(f"{prefix}/submit-results", headers=headers).status_code == 200
    plots = client.post(f"{prefix}/generate-plots", data={"selected_plots": "boxplot"}, headers=headers)
    assert plots.status_code == 200
    assert BeautifulSoup(plots.text, "html.parser").select_one(".plot-result-meta span").get_text(strip=True) == (
        "Method: Independent two-sample t-test"
    )
    assert session.stat_results == original_results
    assert client.post(f"{prefix}/submit-plots", headers=headers).status_code == 200
    state_response = client.get(prefix)
    assert state_response.status_code == 200
    assert state_response.json()["stat_results"] == original_results
    exported = client.post(f"{prefix}/export", json={"export_format": "json"})
    assert exported.status_code == 200
    assert set(exported.json()) == {"dataset", "statistical_results", "plots"}
    assert exported.json()["statistical_results"] == original_results
    assert "display_name" not in exported.text


@pytest.mark.parametrize("htmx", [False, True])
def test_empty_results_remain_renderable(client: TestClient, session: WizardSession, htmx: bool) -> None:
    session.current_step = "results"
    response = client.post(
        f"/wizard/sessions/{session.session_id}/update-sig-limit",
        data={"plots_sig_filter": "0.05"},
        headers={"HX-Request": "true"} if htmx else {},
    )
    assert response.status_code == 200
    assert "No statistical results generated." in response.text
    assert session.stat_results == []
