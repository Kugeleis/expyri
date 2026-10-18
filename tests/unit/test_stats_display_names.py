"""Statistical labels remain separate from stable plugin identifiers."""

import pytest

from app.core.registry import Registry
from app.stats.base import DataProperties, StatMethod, StatResult, stat_registry


class LegacyStat(StatMethod):
    name = "legacy_stat"
    description = "A plugin without a display-name override."

    def is_applicable(self, properties: DataProperties) -> bool:
        return True

    def run(self, groups: dict[str, list[float]]) -> StatResult:
        return StatResult(method_name=self.name, test_statistic=1.0, p_value=0.5, summary="Legacy result.")


class LabelledStat(LegacyStat):
    name = "custom_stat"

    @property
    def display_name(self) -> str:
        return "Custom statistical test"


def test_legacy_display_name_fallback() -> None:
    method = LegacyStat()

    assert method.display_name == "Legacy Stat"
    assert method.name == "legacy_stat"


@pytest.mark.parametrize(
    ("plugin_class", "label"),
    [(LegacyStat, "Legacy Stat"), (LabelledStat, "Custom statistical test")],
)
def test_display_name_preserves_zero_argument_registration(plugin_class: type[StatMethod], label: str) -> None:
    registry: Registry[StatMethod] = Registry("stat")
    registry.register(plugin_class.name)(plugin_class)
    method = registry.get(plugin_class.name)

    assert method.display_name == label
    assert method.name == plugin_class.name
    assert method.run({"A": [1.0], "B": [2.0]}).method_name == plugin_class.name


def test_inherited_display_name_is_read_only() -> None:
    method = LegacyStat()

    with pytest.raises(AttributeError):
        method.display_name = "Changed label"


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
def test_builtin_display_name_preserves_identifier(method_id: str, label: str) -> None:
    method = stat_registry.get(method_id)

    assert method.display_name == label
    assert method.name == method_id
