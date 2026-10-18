"""Significance consumers prefer corrected p-values and retain legacy behavior."""

from typing import Any

import pytest

from app.core.session import WizardSession
from app.wizard.plotting import select_top_plot_columns
from app.wizard.router import dependencies
from app.wizard.statistics import significance_p_value


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        ({"p_value": 0.01, "p_value_adjusted": 0.08}, 0.08),
        ({"p_value": 0.0, "p_value_adjusted": 0.0}, 0.0),
        ({"p_value": 0.02, "p_value_adjusted": None}, 0.02),
        ({"p_value": 0.02}, 0.02),
        ({"p_value": None}, None),
        ({}, None),
    ],
)
def test_significance_p_value_uses_adjusted_value_when_available(
    result: dict[str, Any], expected: float | None
) -> None:
    assert significance_p_value(result) == expected


def test_plot_filter_uses_adjusted_values_with_legacy_fallback() -> None:
    session = WizardSession(
        selected_value_columns=["changed", "significant", "legacy", "zero", "unavailable"],
        stat_results=[
            {"column_name": "changed", "p_value": 0.03, "p_value_adjusted": 0.06},
            {"column_name": "significant", "p_value": 0.01, "p_value_adjusted": 0.03},
            {"column_name": "legacy", "p_value": 0.04},
            {"column_name": "zero", "p_value": 0.0, "p_value_adjusted": 0.0},
            {"column_name": "unavailable", "p_value": None},
        ],
    )
    assert select_top_plot_columns(session, 0.05) == ["significant", "legacy", "zero"]
    assert select_top_plot_columns(session, 0.0) == ["zero"]
    assert select_top_plot_columns(session, 0.05, top_n_columns=1) == ["changed"]


def test_significance_chart_plots_adjusted_values_without_mutating_results(monkeypatch: pytest.MonkeyPatch) -> None:
    results = [
        {"column_name": "changed", "p_value": 0.03, "p_value_adjusted": 0.06},
        {"column_name": "significant", "p_value": 0.009, "p_value_adjusted": 0.027},
        {"column_name": "legacy", "p_value": 0.02},
        {"column_name": "zero", "p_value": 0.0, "p_value_adjusted": 0.0},
        {"column_name": "unavailable", "p_value": None},
    ]
    original = [dict(result) for result in results]
    rendered: dict[str, Any] = {}
    save_plot = dependencies.save_plot

    def capture_chart(fig: Any, *args: Any, **kwargs: Any) -> None:
        ax = fig.axes[0]
        rendered["labels"] = [tick.get_text() for tick in ax.get_xticklabels()]
        rendered["p_values"] = list(ax.collections[0].get_offsets()[:, 1])
        rendered["ylabel"] = ax.get_ylabel()
        save_plot(fig, *args, **kwargs)

    monkeypatch.setattr(dependencies, "save_plot", capture_chart)

    assert dependencies.generate_significance_chart_base64(results, 0.05)
    assert rendered["labels"] == ["zero", "legacy", "significant", "changed"]
    assert rendered["p_values"] == pytest.approx([0.0, 0.02, 0.027, 0.06])
    assert "adjusted" in rendered["ylabel"].lower()
    assert results == original


def test_significance_chart_handles_no_available_p_values() -> None:
    assert dependencies.generate_significance_chart_base64([{"p_value": None}], 0.05) is None
