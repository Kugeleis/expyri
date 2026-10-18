"""Flat submissions correct outcome families without changing raw results."""

from collections.abc import Callable
from pathlib import Path

import pandas as pd
import pytest

from app.core.session import HierarchyConfig, InMemorySessionStore, WizardSession
from app.datasets.repository import CsvDatasetRepository
from app.stats.base import DataProperties, StatMethod, StatResult, stat_registry
from app.wizard.analysis_service import WizardAnalysisService


class FixedPValueMethod(StatMethod):
    name = "fixed_p_value"
    description = "Return a known p-value encoded in the outcome column."

    def is_applicable(self, properties: DataProperties) -> bool:
        return True

    def run(self, groups: dict[str, list[float]]) -> StatResult:
        return StatResult(method_name=self.name, test_statistic=2.0, p_value=groups["A"][0], summary="Raw result")


@pytest.fixture(autouse=True)
def fixed_method(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(stat_registry, "_plugins", stat_registry.list_all())
    stat_registry.register("fixed_p_value")(FixedPValueMethod)


def submit_values(tmp_path: Path, continuous: list[float], discrete: list[float]) -> WizardSession:
    columns = {f"continuous_{i}": [p] * 4 for i, p in enumerate(continuous)}
    columns.update({f"discrete_{i}": [p] * 4 for i, p in enumerate(discrete)})
    pd.DataFrame({"group": ["A", "A", "B", "B"], **columns}).to_csv(tmp_path / "known.csv", index=False)
    store = InMemorySessionStore()
    session = WizardSession(
        dataset_id="known",
        group_column="group",
        current_step="stat_method",
        selected_value_columns=[f"continuous_{i}" for i in range(len(continuous))],
        selected_discrete_columns=[f"discrete_{i}" for i in range(len(discrete))],
    )
    store.save(session)
    service = WizardAnalysisService(store, CsvDatasetRepository(tmp_path))
    result = service.submit_method(
        session.session_id, "fixed_p_value" if continuous else None, "fixed_p_value" if discrete else None
    )
    assert store.get(session.session_id) is result
    assert result.current_step == "results"
    return result


def test_legacy_stat_result_defaults_to_no_correction() -> None:
    result = StatResult(method_name="legacy", test_statistic=2.0, p_value=0.03, summary="Unchanged")
    assert result.p_value_adjusted is None
    assert result.correction_method is None


@pytest.mark.parametrize("family", ["continuous", "discrete"])
@pytest.mark.parametrize(
    ("raw", "adjusted"),
    [
        ([0.01, 0.04, 0.03, 0.002], [0.03, 0.06, 0.06, 0.008]),
        ([0.4, 0.4, 0.9], [1.0, 1.0, 1.0]),
        ([0.0, 1.0], [0.0, 1.0]),
    ],
)
def test_submit_method_applies_holm_in_original_column_order(
    tmp_path: Path, family: str, raw: list[float], adjusted: list[float]
) -> None:
    session = submit_values(tmp_path, raw if family == "continuous" else [], raw if family == "discrete" else [])
    results = {result["column_name"]: result for result in session.stat_results}
    for i, (p_value, expected) in enumerate(zip(raw, adjusted, strict=True)):
        result = results[f"{family}_{i}"]
        assert result["p_value"] == p_value
        assert result["p_value_adjusted"] == pytest.approx(expected)
        assert result["correction_method"] == "holm"
        assert result["test_statistic"] == 2.0
        assert result["summary"] == "Raw result"


def test_submit_method_keeps_continuous_and_discrete_families_separate(tmp_path: Path) -> None:
    session = submit_values(tmp_path, [0.01, 0.04, 0.03], [0.001, 0.02])
    adjusted = {result["column_name"]: result["p_value_adjusted"] for result in session.stat_results}
    assert adjusted == pytest.approx(
        {"continuous_0": 0.03, "continuous_1": 0.06, "continuous_2": 0.06, "discrete_0": 0.002, "discrete_1": 0.02}
    )


@pytest.mark.parametrize("family", ["continuous", "discrete"])
def test_single_result_records_holm_without_changing_p_value(tmp_path: Path, family: str) -> None:
    session = submit_values(tmp_path, [0.03] if family == "continuous" else [], [0.03] if family == "discrete" else [])
    result = session.stat_results[0]
    assert result["p_value_adjusted"] == result["p_value"] == 0.03
    assert result["correction_method"] == "holm"


def test_resubmission_corrects_only_current_raw_results(tmp_path: Path) -> None:
    session = submit_values(tmp_path, [0.01, 0.04, 0.03], [0.02])
    previous_results = [dict(result) for result in session.stat_results]
    store = InMemorySessionStore()
    store.save(session)
    service = WizardAnalysisService(store, CsvDatasetRepository(tmp_path))

    updated = service.submit_method(session.session_id, "fixed_p_value", "fixed_p_value")

    assert updated.stat_results == previous_results


def test_hierarchical_submission_preserves_primary_and_posthoc_results(
    tmp_path: Path, hierarchical_df: Callable[..., pd.DataFrame]
) -> None:
    from app.wizard.statistics import run_stat_for_column

    df = hierarchical_df(n_groups=3)
    df["metric2"] = df["metric"] + 100
    df.to_csv(tmp_path / "hierarchical.csv", index=False)
    repo = CsvDatasetRepository(tmp_path)
    store = InMemorySessionStore()
    session = WizardSession(
        dataset_id="hierarchical",
        group_column="group",
        current_step="stat_method",
        selected_value_columns=["metric", "metric2"],
        hierarchy=HierarchyConfig(group_col="group", cluster_col="cluster"),
    )
    store.save(session)
    method = stat_registry.get("cluster_mean_anova")
    loaded_df = repo.load_dataset("hierarchical")
    expected = {
        column: run_stat_for_column(loaded_df, column, method, session).model_dump()
        for column in session.selected_value_columns
    }

    result = WizardAnalysisService(store, repo).submit_method(session.session_id, method.name, None)

    for record in result.stat_results:
        assert record == expected[record["column_name"]]
        assert record["p_value_adjusted"] is None
        assert record["correction_method"] is None
        assert record["posthoc"]
