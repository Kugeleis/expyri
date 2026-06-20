"""Unit tests for the statistical methods and data properties computation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import scipy.stats as stats

from app.stats.base import DataProperties, compute_data_properties, stat_registry
from app.stats.builtin.anova import Anova
from app.stats.builtin.kruskal_wallis import KruskalWallis
from app.stats.builtin.mann_whitney import MannWhitney
from app.stats.builtin.ttest import TTestInd


@pytest.fixture
def normal_groups_df() -> pd.DataFrame:
    """Return a DataFrame with two normally distributed groups."""
    np.random.seed(42)
    g1 = np.random.normal(loc=10.0, scale=1.0, size=20)
    g2 = np.random.normal(loc=11.0, scale=1.0, size=20)
    df = pd.DataFrame(
        {
            "group": ["A"] * 20 + ["B"] * 20,
            "value": np.concatenate([g1, g2]),
        }
    )
    return df


@pytest.fixture
def three_groups_df() -> pd.DataFrame:
    """Return a DataFrame with three normally distributed groups."""
    np.random.seed(42)
    g1 = np.random.normal(loc=10.0, scale=1.0, size=15)
    g2 = np.random.normal(loc=11.0, scale=1.0, size=15)
    g3 = np.random.normal(loc=12.0, scale=1.0, size=15)
    df = pd.DataFrame(
        {
            "group": ["A"] * 15 + ["B"] * 15 + ["C"] * 15,
            "value": np.concatenate([g1, g2, g3]),
        }
    )
    return df


def test_registrations() -> None:
    """Verify built-in statistical methods are registered."""
    assert isinstance(stat_registry.get("ttest_ind"), TTestInd)
    assert isinstance(stat_registry.get("mann_whitney"), MannWhitney)
    assert isinstance(stat_registry.get("anova"), Anova)
    assert isinstance(stat_registry.get("kruskal_wallis"), KruskalWallis)


def test_compute_data_properties_valid(normal_groups_df: pd.DataFrame) -> None:
    """Test compute_data_properties with valid data."""
    props = compute_data_properties(normal_groups_df, "group", "value")

    assert props.n_groups == 2
    assert props.group_sizes == {"A": 20, "B": 20}
    # For normally distributed data, shapiro p should be > 0.05
    assert props.normality["A"] > 0.05
    assert props.normality["B"] > 0.05
    # Variance homogeneity should be > 0.05
    assert props.variance_homogeneity > 0.05


def test_compute_data_properties_invalid_inputs(normal_groups_df: pd.DataFrame) -> None:
    """Test compute_data_properties with invalid columns."""
    with pytest.raises(ValueError, match="Group column"):
        compute_data_properties(normal_groups_df, "missing_col", "value")

    with pytest.raises(ValueError, match="Value column"):
        compute_data_properties(normal_groups_df, "group", "missing_col")

    # Value column not numeric
    df_non_numeric = normal_groups_df.copy()
    df_non_numeric["value"] = "string_value"
    with pytest.raises(ValueError, match="must be numeric"):
        compute_data_properties(df_non_numeric, "group", "value")


def test_compute_data_properties_small_groups() -> None:
    """Test compute_data_properties behavior on small groups (< 3 samples)."""
    df = pd.DataFrame(
        {
            "group": ["A", "A", "B", "B"],
            "value": [1.0, 2.0, 1.5, 2.5],
        }
    )
    props = compute_data_properties(df, "group", "value")
    # Shapiro-Wilk needs >= 3 samples, so normality p-value should default to 0.0
    assert props.normality["A"] == 0.0
    assert props.normality["B"] == 0.0


def test_ttest_applicability() -> None:
    """Test ttest_ind applicability rules."""
    ttest = TTestInd()

    # Applicable: 2 normal groups, size >= 2
    props_valid = DataProperties(
        n_groups=2,
        group_sizes={"A": 10, "B": 10},
        normality={"A": 0.5, "B": 0.6},
        variance_homogeneity=0.8,
    )
    assert ttest.is_applicable(**props_valid.model_dump()) is True

    # Inapplicable: 3 groups
    props_three_groups = DataProperties(
        n_groups=3,
        group_sizes={"A": 10, "B": 10, "C": 10},
        normality={"A": 0.5, "B": 0.6, "C": 0.7},
        variance_homogeneity=0.8,
    )
    assert ttest.is_applicable(**props_three_groups.model_dump()) is False

    # Inapplicable: Small group size (< 2)
    props_small = DataProperties(
        n_groups=2,
        group_sizes={"A": 1, "B": 10},
        normality={"A": 0.5, "B": 0.6},
        variance_homogeneity=0.8,
    )
    assert ttest.is_applicable(**props_small.model_dump()) is False

    # Inapplicable: Non-normal group
    props_non_normal = DataProperties(
        n_groups=2,
        group_sizes={"A": 10, "B": 10},
        normality={"A": 0.01, "B": 0.6},
        variance_homogeneity=0.8,
    )
    assert ttest.is_applicable(**props_non_normal.model_dump()) is False


def test_ttest_run(normal_groups_df: pd.DataFrame) -> None:
    """Test running ttest_ind against scipy reference."""
    ttest = TTestInd()
    gA = normal_groups_df[normal_groups_df["group"] == "A"]["value"].tolist()
    gB = normal_groups_df[normal_groups_df["group"] == "B"]["value"].tolist()

    res = ttest.run({"A": gA, "B": gB})
    ref_stat, ref_p = stats.ttest_ind(gA, gB, equal_var=True)

    assert res.method_name == "ttest_ind"
    assert pytest.approx(res.test_statistic) == ref_stat
    assert pytest.approx(res.p_value) == ref_p
    assert res.effect_size is not None
    assert res.effect_size < 0  # Group A mean is lower than B in the seed


def test_ttest_run_errors() -> None:
    """Test ttest_ind run error states."""
    ttest = TTestInd()
    with pytest.raises(ValueError, match="requires exactly 2 groups"):
        ttest.run({"A": [1.0, 2.0]})

    with pytest.raises(ValueError, match="at least 2 samples"):
        ttest.run({"A": [1.0], "B": [1.0, 2.0]})


def test_mann_whitney_applicability() -> None:
    """Test mann_whitney applicability rules."""
    mw = MannWhitney()

    # Applicable: 2 groups, size >= 2, normality doesn't matter
    props_valid = DataProperties(
        n_groups=2,
        group_sizes={"A": 10, "B": 10},
        normality={"A": 0.01, "B": 0.02},
        variance_homogeneity=0.8,
    )
    assert mw.is_applicable(**props_valid.model_dump()) is True

    # Inapplicable: 3 groups
    props_three_groups = DataProperties(
        n_groups=3,
        group_sizes={"A": 10, "B": 10, "C": 10},
        normality={"A": 0.5, "B": 0.6, "C": 0.7},
        variance_homogeneity=0.8,
    )
    assert mw.is_applicable(**props_three_groups.model_dump()) is False

    # Inapplicable: Small group size
    props_small = DataProperties(
        n_groups=2,
        group_sizes={"A": 1, "B": 10},
        normality={"A": 0.5, "B": 0.6},
        variance_homogeneity=0.8,
    )
    assert mw.is_applicable(**props_small.model_dump()) is False


def test_mann_whitney_run(normal_groups_df: pd.DataFrame) -> None:
    """Test running mann_whitney against scipy reference."""
    mw = MannWhitney()
    gA = normal_groups_df[normal_groups_df["group"] == "A"]["value"].tolist()
    gB = normal_groups_df[normal_groups_df["group"] == "B"]["value"].tolist()

    res = mw.run({"A": gA, "B": gB})
    ref_stat, ref_p = stats.mannwhitneyu(gA, gB, alternative="two-sided")

    assert res.method_name == "mann_whitney"
    assert pytest.approx(res.test_statistic) == ref_stat
    assert pytest.approx(res.p_value) == ref_p
    assert res.effect_size is not None


def test_mann_whitney_run_errors() -> None:
    """Test mann_whitney run error states."""
    mw = MannWhitney()
    with pytest.raises(ValueError, match="requires exactly 2 groups"):
        mw.run({"A": [1.0, 2.0]})

    with pytest.raises(ValueError, match="at least 2 samples"):
        mw.run({"A": [1.0], "B": [1.0, 2.0]})


def test_anova_applicability() -> None:
    """Test anova applicability rules."""
    anova = Anova()

    # Applicable: >= 2 groups, size >= 2, normal, homogeneous
    props_valid = DataProperties(
        n_groups=3,
        group_sizes={"A": 10, "B": 10, "C": 10},
        normality={"A": 0.5, "B": 0.6, "C": 0.7},
        variance_homogeneity=0.8,
    )
    assert anova.is_applicable(**props_valid.model_dump()) is True

    # Inapplicable: < 2 groups
    props_one_group = DataProperties(
        n_groups=1,
        group_sizes={"A": 10},
        normality={"A": 0.5},
        variance_homogeneity=1.0,
    )
    assert anova.is_applicable(**props_one_group.model_dump()) is False

    # Inapplicable: Small group size
    props_small = DataProperties(
        n_groups=3,
        group_sizes={"A": 1, "B": 10, "C": 10},
        normality={"A": 0.5, "B": 0.6, "C": 0.7},
        variance_homogeneity=0.8,
    )
    assert anova.is_applicable(**props_small.model_dump()) is False

    # Inapplicable: Non-normal
    props_non_normal = DataProperties(
        n_groups=3,
        group_sizes={"A": 10, "B": 10, "C": 10},
        normality={"A": 0.01, "B": 0.6, "C": 0.7},
        variance_homogeneity=0.8,
    )
    assert anova.is_applicable(**props_non_normal.model_dump()) is False

    # Inapplicable: Heterogeneous variance
    props_hetero = DataProperties(
        n_groups=3,
        group_sizes={"A": 10, "B": 10, "C": 10},
        normality={"A": 0.5, "B": 0.6, "C": 0.7},
        variance_homogeneity=0.02,
    )
    assert anova.is_applicable(**props_hetero.model_dump()) is False


def test_anova_run(three_groups_df: pd.DataFrame) -> None:
    """Test running anova against scipy reference."""
    anova = Anova()
    gA = three_groups_df[three_groups_df["group"] == "A"]["value"].tolist()
    gB = three_groups_df[three_groups_df["group"] == "B"]["value"].tolist()
    gC = three_groups_df[three_groups_df["group"] == "C"]["value"].tolist()

    res = anova.run({"A": gA, "B": gB, "C": gC})
    ref_stat, ref_p = stats.f_oneway(gA, gB, gC)

    assert res.method_name == "anova"
    assert pytest.approx(res.test_statistic) == ref_stat
    assert pytest.approx(res.p_value) == ref_p
    assert res.effect_size is not None
    assert 0.0 <= res.effect_size <= 1.0


def test_anova_run_errors() -> None:
    """Test anova run error states."""
    anova = Anova()
    with pytest.raises(ValueError, match="requires at least 2 groups"):
        anova.run({"A": [1.0, 2.0]})

    with pytest.raises(ValueError, match="at least 2 samples"):
        anova.run({"A": [1.0], "B": [1.0, 2.0]})


def test_kruskal_wallis_applicability() -> None:
    """Test kruskal_wallis applicability rules."""
    kw = KruskalWallis()

    # Applicable: >= 2 groups, size >= 2
    props_valid = DataProperties(
        n_groups=3,
        group_sizes={"A": 10, "B": 10, "C": 10},
        normality={"A": 0.01, "B": 0.02, "C": 0.03},
        variance_homogeneity=0.01,
    )
    assert kw.is_applicable(**props_valid.model_dump()) is True

    # Inapplicable: < 2 groups
    props_one_group = DataProperties(
        n_groups=1,
        group_sizes={"A": 10},
        normality={"A": 0.5},
        variance_homogeneity=1.0,
    )
    assert kw.is_applicable(**props_one_group.model_dump()) is False

    # Inapplicable: Small group size
    props_small = DataProperties(
        n_groups=3,
        group_sizes={"A": 1, "B": 10, "C": 10},
        normality={"A": 0.5, "B": 0.6, "C": 0.7},
        variance_homogeneity=0.8,
    )
    assert kw.is_applicable(**props_small.model_dump()) is False


def test_kruskal_wallis_run(three_groups_df: pd.DataFrame) -> None:
    """Test running kruskal_wallis against scipy reference."""
    kw = KruskalWallis()
    gA = three_groups_df[three_groups_df["group"] == "A"]["value"].tolist()
    gB = three_groups_df[three_groups_df["group"] == "B"]["value"].tolist()
    gC = three_groups_df[three_groups_df["group"] == "C"]["value"].tolist()

    res = kw.run({"A": gA, "B": gB, "C": gC})
    ref_stat, ref_p = stats.kruskal(gA, gB, gC)

    assert res.method_name == "kruskal_wallis"
    assert pytest.approx(res.test_statistic) == ref_stat
    assert pytest.approx(res.p_value) == ref_p
    assert res.effect_size is not None


def test_kruskal_wallis_run_errors() -> None:
    """Test kruskal_wallis run error states."""
    kw = KruskalWallis()
    with pytest.raises(ValueError, match="requires at least 2 groups"):
        kw.run({"A": [1.0, 2.0]})

    with pytest.raises(ValueError, match="at least 2 samples"):
        kw.run({"A": [1.0], "B": [1.0, 2.0]})
