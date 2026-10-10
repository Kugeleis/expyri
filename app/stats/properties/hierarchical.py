from collections.abc import Callable, Hashable
from typing import Any, Literal, cast

import numpy as np
import pandas as pd
import scipy.stats as stats

from app.core.session import HierarchyConfig
from app.stats.models import DataProperties, NormalityResult, OutlierSummary, VarianceHomogeneityResult
from app.stats.properties.flat import compute_missing_summary

MetricKind = Literal["continuous", "binary_proportion", "unsupported"]


def _quantile_05(values: pd.Series) -> float:
    """5th percentile of a value series."""
    return float(values.quantile(0.05))


def _quantile_95(values: pd.Series) -> float:
    """95th percentile of a value series."""
    return float(values.quantile(0.95))


def _interquartile_range(values: pd.Series) -> float:
    """Interquartile range (Q3 - Q1) of a value series."""
    return float(values.quantile(0.75) - values.quantile(0.25))


def _filter_unit_data(
    unit_df: pd.DataFrame,
    config: HierarchyConfig,
    excluded_clusters: list[str],
    metric: str,
) -> pd.DataFrame:
    """Drop excluded clusters and rows missing group/cluster/metric values."""
    excluded_mask: pd.Series[bool] = unit_df[config.cluster_col].astype(str).isin(excluded_clusters)
    filtered: pd.DataFrame = unit_df[~excluded_mask]
    return filtered.dropna(subset=[config.group_col, config.cluster_col, metric])


def _aggregate_continuous(unit_df: pd.DataFrame, config: HierarchyConfig, metric: str) -> pd.DataFrame:
    """Aggregate unit-level values into continuous per-cluster summaries."""
    return (
        unit_df.groupby([config.group_col, config.cluster_col])[metric]
        .agg(
            mean="mean",
            median="median",
            std="std",
            iqr=_interquartile_range,
            p5=_quantile_05,
            p95=_quantile_95,
            n_units="count",
        )
        .reset_index()
    )


def _aggregate_proportion(unit_df: pd.DataFrame, config: HierarchyConfig, metric: str) -> pd.DataFrame:
    """Aggregate unit-level binary values into per-cluster proportions.

    ``proportion_corrected`` applies a half-unit continuity correction so
    observed proportions of 0 and 1 are pulled towards the interval centre,
    keeping log-odds style downstream analyses finite.
    """
    agg_df: pd.DataFrame = (
        unit_df.groupby([config.group_col, config.cluster_col])[metric].agg(n_pass="sum", n_units="count").reset_index()
    )
    agg_df["proportion_raw"] = agg_df["n_pass"] / agg_df["n_units"]
    agg_df["proportion_corrected"] = np.clip(
        agg_df["proportion_raw"], 0.5 / agg_df["n_units"], 1.0 - 0.5 / agg_df["n_units"]
    )
    return agg_df


def _aggregate_unsupported(unit_df: pd.DataFrame, config: HierarchyConfig, metric: str) -> pd.DataFrame:
    """Return an empty aggregate frame for metrics that cannot be summarized."""
    del unit_df, metric
    return pd.DataFrame(columns=[config.group_col, config.cluster_col])


_AGGREGATORS: dict[MetricKind, Callable[[pd.DataFrame, HierarchyConfig, str], pd.DataFrame]] = {
    "continuous": _aggregate_continuous,
    "binary_proportion": _aggregate_proportion,
    "unsupported": _aggregate_unsupported,
}


def build_cluster_aggregates(
    unit_df: pd.DataFrame,
    config: HierarchyConfig,
    excluded_clusters: list[str],
    metric: str,
    metric_kind: MetricKind,
) -> pd.DataFrame:
    """Build cluster-level aggregates from unit-level data.

    Excluded clusters and rows with missing group/cluster/metric values are
    dropped before aggregation; fully filtered input yields an empty frame
    carrying the columns of the requested metric kind.
    """
    filtered = _filter_unit_data(unit_df, config, excluded_clusters, metric)
    return _AGGREGATORS[metric_kind](filtered, config, metric)


def run_iterative_grubbs(df: pd.DataFrame, cluster_col: str, value_col: str, alpha: float = 0.05) -> list[str]:
    """Iteratively detect outliers using Grubbs test on cluster means."""
    temp_df: pd.DataFrame = df[[cluster_col, value_col]].dropna().copy()
    outliers: list[str] = []

    while len(temp_df) >= 3:
        n: int = len(temp_df)
        mean_val: float = temp_df[value_col].mean()
        std_val: float = temp_df[value_col].std()
        if std_val == 0 or np.isnan(std_val):
            break

        dev: pd.Series = (temp_df[value_col] - mean_val).abs()
        max_idx: Hashable = dev.idxmax()
        max_row = temp_df.loc[cast(Any, max_idx)]
        g_val = float(dev.max()) / std_val

        t_dist = stats.t.ppf(1 - alpha / (2 * n), n - 2)
        g_crit = ((n - 1) / np.sqrt(n)) * np.sqrt(t_dist**2 / (n - 2 + t_dist**2))

        if g_val > g_crit:
            outliers.append(str(max_row[cluster_col]))
            temp_df = temp_df.drop(max_idx)
        else:
            break

    return outliers


def compute_quick_icc(df: pd.DataFrame, cluster_col: str, metric: str) -> float:
    """Calculate Intra-class Correlation (ICC) using a fast ANOVA-based method."""
    clean_df = df[[cluster_col, metric]].dropna()
    k_unique = clean_df[cluster_col].nunique()
    n_total = len(clean_df)
    if k_unique < 2 or n_total < 3:
        return float("nan")

    try:
        # Calculate cluster sizes (n_i)
        sizes = clean_df.groupby(cluster_col)[metric].count()
        if (sizes <= 1).all():
            return 0.0

        # Overall mean
        grand_mean = float(clean_df[metric].mean())

        # Sum of squares between (SSB)
        cluster_means = clean_df.groupby(cluster_col)[metric].mean()
        ssb = float(((cluster_means - grand_mean) ** 2 * sizes).sum())

        # Sum of squares within (SSW)
        cluster_vars = clean_df.groupby(cluster_col)[metric].var(ddof=1)
        ssw = float(((sizes - 1) * cluster_vars.fillna(0)).sum())

        df_b = k_unique - 1
        df_w = n_total - k_unique

        if df_w <= 0:
            return float("nan")

        msb = ssb / df_b
        msw = ssw / df_w

        # k0 adjustment for unequal sizes: k0 = (N - sum(n_i^2)/N) / (K - 1)
        sum_sq_sizes = float((sizes**2).sum())
        k0 = (n_total - (sum_sq_sizes / n_total)) / df_b

        if k0 <= 0:
            return float("nan")

        denominator = msb + (k0 - 1) * msw
        if denominator == 0:
            return 0.0

        icc = (msb - msw) / denominator
        # Clip ICC to range [0.0, 1.0] since variance components are non-negative
        return max(0.0, min(1.0, float(icc)))
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return float("nan")


def compute_hierarchical_properties(  # noqa: C901
    df: pd.DataFrame,
    config: HierarchyConfig,
    excluded_clusters: list[str],
    metric: str,
) -> DataProperties:
    """Compute properties for a hierarchical dataset."""
    unique_vals = set(df[metric].dropna().unique())
    is_numeric = bool(pd.api.types.is_numeric_dtype(df[metric]))
    is_boolean = pd.api.types.is_bool_dtype(df[metric])
    if unique_vals.issubset({0, 1}) and len(unique_vals) > 0:
        metric_kind: MetricKind = "binary_proportion"
    elif is_numeric or is_boolean:
        metric_kind = "continuous"
    else:
        metric_kind = "unsupported"

    agg_df = build_cluster_aggregates(df, config, excluded_clusters, metric, metric_kind)

    clean_unit = _filter_unit_data(df, config, excluded_clusters, metric)

    group_sizes: dict[str, int] = {
        str(g_name): int(g_size) for g_name, g_size in clean_unit.groupby(config.group_col).size().items()
    }

    n_groups = len(group_sizes)

    n_clusters_per_group: dict[str, int] = {}
    n_units_per_cluster: dict[str, int] = {}
    if not agg_df.empty:
        n_clusters_per_group = {
            str(g_name): int(n_clusters)
            for g_name, n_clusters in agg_df.groupby(config.group_col)[config.cluster_col].nunique().items()
        }
        n_units_per_cluster = {
            str(cluster_id): int(n_units)
            for cluster_id, n_units in agg_df.set_index(config.cluster_col)["n_units"].items()
        }

    min_clusters_per_group = min(n_clusters_per_group.values()) if n_clusters_per_group else 0

    normality_cluster_means = False
    homogeneity_cluster = False
    outlier_clusters: list[str] = []
    normality_results = {}
    var_homogeneity_result = None

    if metric_kind == "continuous":
        normality_cluster_means = True
        if not agg_df.empty:
            grouped_agg = agg_df.groupby(config.group_col)
            for g_name, g_df in grouped_agg:
                vals = g_df["mean"].dropna().values
                n = len(vals)
                if n < 3:
                    is_normal = False
                    test_used = "None"
                    p_val = None
                    note = "Insufficient clusters (n < 3)"
                    normality_cluster_means = False
                else:
                    test_used = "Shapiro-Wilk"
                    try:
                        _, p_val_stat = stats.shapiro(vals)
                        p_val = float(p_val_stat)
                        is_normal = p_val > 0.05
                        note = None
                        if not is_normal:
                            normality_cluster_means = False
                    except (RuntimeError, TypeError, ValueError) as e:
                        p_val = None
                        is_normal = False
                        note = f"Shapiro-Wilk failed: {e}"
                        normality_cluster_means = False

                normality_results[str(g_name)] = NormalityResult(
                    test_used=test_used, p_value=p_val, n=n, is_normal=is_normal, note=note
                )
        else:
            normality_cluster_means = False

        if not agg_df.empty:
            grouped_agg = agg_df.groupby(config.group_col)
            group_means = [g_df["mean"].dropna().values for _, g_df in grouped_agg]
            group_means = [arr for arr in group_means if len(arr) >= 2]
            if len(group_means) >= 2:
                try:
                    stat, p_val = stats.levene(*group_means, center="median")
                    p_val_float = float(p_val)
                    if not np.isnan(p_val_float):
                        homogeneity_cluster = p_val_float > 0.05
                        var_homogeneity_result = VarianceHomogeneityResult(
                            test_used="Levene",
                            statistic=float(stat),
                            p_value=p_val_float,
                            equal_variances=homogeneity_cluster,
                        )
                except (RuntimeError, TypeError, ValueError):
                    var_homogeneity_result = None

        if min_clusters_per_group >= 4 and not agg_df.empty:
            outlier_clusters = run_iterative_grubbs(agg_df, config.cluster_col, "mean")

    has_boundary_clusters = False
    boundary_cluster_ids: list[str] = []
    if metric_kind == "binary_proportion" and not agg_df.empty:
        boundary_mask = agg_df["proportion_raw"].isin([0.0, 1.0])
        boundary_cluster_ids = agg_df[boundary_mask][config.cluster_col].astype(str).tolist()
        has_boundary_clusters = len(boundary_cluster_ids) > 0

    icc = float("nan") if metric_kind == "unsupported" else compute_quick_icc(clean_unit, config.cluster_col, metric)

    power_at_observed_n = 0.0
    if min_clusters_per_group >= 2:
        try:
            from statsmodels.stats.power import TTestIndPower

            analysis = TTestIndPower()
            power_at_observed_n = float(
                analysis.solve_power(
                    effect_size=0.8, nobs1=min_clusters_per_group, ratio=1.0, alpha=0.05, alternative="two-sided"
                )
            )
        except (ImportError, RuntimeError, TypeError, ValueError):
            power_at_observed_n = 0.0
    power_warning = power_at_observed_n < 0.8

    outliers_dict = {}
    if metric_kind == "continuous" and not agg_df.empty:
        outliers_dict = {"outlier_clusters": OutlierSummary(count=len(outlier_clusters), indices=outlier_clusters)}

    missing = compute_missing_summary(df, metric, config.group_col)

    small_groups = [g for g, size in group_sizes.items() if size < 5]
    sample_size_warning = None
    if small_groups:
        groups_str = ", ".join(small_groups)
        sample_size_warning = f"Warning: The following groups have small sample sizes (n < 5): {groups_str}."

    return DataProperties(
        outcome_type_guess="continuous" if metric_kind == "continuous" else "categorical_nominal",
        is_numeric=is_numeric,
        n_groups=n_groups,
        group_sizes=group_sizes,
        normality=normality_results,
        all_groups_normal=normality_cluster_means if metric_kind == "continuous" else False,
        variance_homogeneity=var_homogeneity_result,
        expected_cell_counts=None,
        min_expected_cell_count=None,
        sphericity=None,
        missing=missing,
        outliers=outliers_dict,
        sample_size_warning=sample_size_warning,
        sampled=False,
        has_hierarchy=True,
        has_spatial_coords=config.x_col is not None and config.y_col is not None,
        n_clusters_per_group=n_clusters_per_group,
        min_clusters_per_group=min_clusters_per_group,
        n_units_per_cluster=n_units_per_cluster,
        metric_kind=metric_kind,
        normality_cluster_means=normality_cluster_means,
        homogeneity_cluster=homogeneity_cluster,
        outlier_clusters=outlier_clusters,
        has_boundary_clusters=has_boundary_clusters,
        boundary_cluster_ids=boundary_cluster_ids,
        icc=icc,
        power_at_observed_n=power_at_observed_n,
        power_warning=power_warning,
    )
