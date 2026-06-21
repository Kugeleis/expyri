"""Statistical method base classes and utilities.

All statistical methods must inherit from ``StatMethod`` and register
themselves using the global ``stat_registry``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np
import pandas as pd
import scipy.stats as stats
from pydantic import BaseModel, Field, model_validator

from app.core.registry import Registry


class NormalityResult(BaseModel):
    """Result of a normality test for a single group."""

    test_used: str = Field(..., description="Name of the test used.")
    p_value: float | None = Field(None, description="Normality test p-value.")
    n: int = Field(..., description="Sample size of the group.")
    is_normal: bool = Field(..., description="Whether normality is assumed.")
    note: str | None = Field(None, description="Optional warning/error note.")


class VarianceHomogeneityResult(BaseModel):
    """Result of a variance homogeneity test."""

    test_used: str = Field("Levene", description="Name of the test used.")
    statistic: float = Field(..., description="Calculated test statistic.")
    p_value: float = Field(..., description="Calculated p-value.")
    equal_variances: bool = Field(..., description="Whether variances are homogeneous.")


class SphericityResult(BaseModel):
    """Result of a sphericity test (e.g. Mauchly)."""

    statistic: float = Field(..., description="Mauchly's W statistic.")
    p_value: float = Field(..., description="Calculated p-value.")
    sphericity_assumed: bool = Field(..., description="Whether sphericity is assumed.")
    note: str | None = Field(None, description="Optional explanation or warning.")


class MissingColumnSummary(BaseModel):
    """Summary of missing values in a column."""

    count: int = Field(..., description="Number of missing values.")
    percentage: float = Field(..., description="Percentage of missing values.")


class MissingnessAssociationResult(BaseModel):
    """Result of the association check between outcome missingness and group."""

    test_used: str = Field("Chi-Square", description="Name of the test used.")
    statistic: float | None = Field(None, description="Calculated test statistic.")
    p_value: float | None = Field(None, description="Calculated p-value.")
    significant: bool | None = Field(None, description="Whether the association is significant.")
    note: str | None = Field(None, description="Optional explanation or error note.")


class MissingDataSummary(BaseModel):
    """Summary of missing data in the dataset."""

    outcome_missing: MissingColumnSummary = Field(..., description="Missingness in the outcome column.")
    group_missing: MissingColumnSummary = Field(..., description="Missingness in the group column.")
    association: MissingnessAssociationResult = Field(..., description="Missingness association result.")


class OutlierSummary(BaseModel):
    """Summary of outliers in a single group."""

    count: int = Field(..., description="Number of outliers.")
    indices: list[Any] = Field(..., description="Indices of the outliers in the DataFrame.")


class DataProperties(BaseModel):
    """Properties characterizing a dataset for statistical method applicability."""

    outcome_type_guess: str = Field(
        ...,
        description=("Guessed outcome type (continuous, categorical_nominal, categorical_ordinal_unclear)."),
    )
    n_groups: int = Field(..., description="Number of distinct groups.")
    group_sizes: dict[str, int] = Field(..., description="Size of each group after removing NaNs.")
    normality: dict[str, NormalityResult] = Field(..., description="Normality test result for each group.")
    all_groups_normal: bool = Field(..., description="Whether all groups are normal.")
    variance_homogeneity: VarianceHomogeneityResult | None = Field(
        None, description="Levene's test result, or None if outcome is categorical."
    )
    expected_cell_counts: list[list[float]] | None = Field(None, description="Expected cell counts contingency table.")
    min_expected_cell_count: float | None = Field(None, description="Minimum expected cell count.")
    sphericity: SphericityResult | None = Field(None, description="Mauchly's sphericity test result.")
    missing: MissingDataSummary = Field(..., description="Missing data summary.")
    outliers: dict[str, OutlierSummary] = Field(default_factory=dict, description="Outliers per group.")
    sample_size_warning: str | None = Field(None, description="Warning if any group has sample size < 5.")
    sampled: bool = Field(False, description="Whether the data was sampled.")

    @model_validator(mode="before")
    @classmethod
    def convert_old_format(cls, data: Any) -> Any:
        """Validator to map the old properties structure to the new nested format."""
        if not isinstance(data, dict):
            return data

        # Shallow copy to avoid side-effects
        data = dict(data)
        _convert_old_normality(data)
        _convert_old_variance_homogeneity(data)
        _set_defaults_for_missing_fields(data)

        return data


def _convert_old_normality(data: dict[str, Any]) -> None:
    norm = data.get("normality")
    if not isinstance(norm, dict):
        return
    new_norm = {}
    for k, v in norm.items():
        if isinstance(v, (int, float)):
            g_sizes = data.get("group_sizes", {})
            n_val = g_sizes.get(k, 10) if isinstance(g_sizes, dict) else 10
            new_norm[k] = {
                "test_used": "Shapiro-Wilk",
                "p_value": float(v),
                "n": n_val,
                "is_normal": float(v) > 0.05,
            }
        else:
            new_norm[k] = v
    data["normality"] = new_norm


def _convert_old_variance_homogeneity(data: dict[str, Any]) -> None:
    vh = data.get("variance_homogeneity")
    if isinstance(vh, (int, float)):
        data["variance_homogeneity"] = {
            "test_used": "Levene",
            "statistic": 0.0,
            "p_value": float(vh),
            "equal_variances": float(vh) > 0.05,
        }


def _get_all_groups_normal(norm: Any) -> bool:
    if not isinstance(norm, dict):
        return False
    for v in norm.values():
        if isinstance(v, dict):
            if not v.get("is_normal", False):
                return False
        elif hasattr(v, "is_normal"):
            if not v.is_normal:
                return False
        else:
            return False
    return True


def _set_defaults_for_missing_fields(data: dict[str, Any]) -> None:
    if "outcome_type_guess" not in data:
        data["outcome_type_guess"] = "continuous"
    if "all_groups_normal" not in data:
        data["all_groups_normal"] = _get_all_groups_normal(data.get("normality", {}))
    if "missing" not in data:
        data["missing"] = {
            "outcome_missing": {"count": 0, "percentage": 0.0},
            "group_missing": {"count": 0, "percentage": 0.0},
            "association": {
                "test_used": "Chi-Square",
                "statistic": None,
                "p_value": None,
                "significant": None,
                "note": "Default values",
            },
        }
    if "outliers" not in data:
        data["outliers"] = {}
    if "sampled" not in data:
        data["sampled"] = False


class StatResult(BaseModel):
    """The result of executing a statistical method."""

    column_name: str | None = Field(
        None,
        description=("Name of the dependent variable column analyzed by this statistical result."),
    )

    method_name: str = Field(..., description="Name of the statistical method.")
    test_statistic: float = Field(..., description="Calculated test statistic.")
    p_value: float = Field(..., description="Calculated p-value.")
    effect_size: float | None = Field(None, description="Optional calculated effect size.")
    summary: str = Field(..., description="Human-readable text summary of results.")


class StatMethod(ABC):
    """Abstract base class for all statistical evaluation methods."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the unique name of the statistical method."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Return a brief description of the statistical method."""
        ...

    @abstractmethod
    def is_applicable(self, **properties: Any) -> bool:
        """Determine whether this method is applicable to the given data properties.

        Args:
            **properties: Keyword arguments representing data properties.

        Returns:
            True if the method can be run on this data, False otherwise.
        """
        ...

    @abstractmethod
    def run(self, groups: dict[str, list[float]]) -> StatResult:
        """Run the statistical method on the grouped data.

        Args:
            groups: A dictionary mapping group names to lists of numeric values.

        Returns:
            A StatResult containing the test statistic, p-value, etc.
        """
        ...


stat_registry: Registry[StatMethod] = Registry("stat")


def guess_outcome_type(series: pd.Series) -> str:
    """Guess the outcome column's statistical variable type.

    Numeric dtype with >10 unique values -> "continuous".
    Numeric or string dtype with <=10 unique values -> "categorical_nominal" by
    default. If integer with a small contiguous range (e.g. 1-5, 1-7), ->
    "categorical_ordinal_unclear".
    """
    clean_series = series.dropna()
    n_unique = clean_series.nunique()

    if n_unique == 0:
        return "categorical_nominal"

    is_numeric = pd.api.types.is_numeric_dtype(series)

    if is_numeric and n_unique > 10:
        return "continuous"

    if is_numeric:
        try:
            is_integer = bool(np.all(clean_series == clean_series.astype(int)))
        except (ValueError, TypeError, OverflowError):
            is_integer = False

        if is_integer:
            val_min = int(clean_series.min())
            val_max = int(clean_series.max())
            if val_max - val_min + 1 == n_unique:
                return "categorical_ordinal_unclear"

    return "categorical_nominal"


def compute_normality(df: pd.DataFrame, outcome_col: str, group_col: str) -> dict[str, NormalityResult]:
    """Compute Shapiro-Wilk or D'Agostino-Pearson normality tests per group."""
    results = {}
    grouped = df.groupby(group_col)[outcome_col]
    for name, group_series in grouped:
        name_str = str(name)
        vals = group_series.dropna().values
        n = len(vals)
        if n < 3:
            results[name_str] = NormalityResult(
                test_used="None",
                p_value=None,
                n=n,
                is_normal=False,
                note="Insufficient data (n < 3)",
            )
            continue

        if n <= 5000:
            test_used = "Shapiro-Wilk"
            try:
                _, p_val = stats.shapiro(vals)
                p_val_float = float(p_val)
                is_normal = p_val_float > 0.05
                note = None
            except Exception as e:
                p_val_float = None
                is_normal = False
                note = f"Shapiro-Wilk failed: {e}"
        else:
            test_used = "D'Agostino-Pearson"
            try:
                _, p_val = stats.normaltest(vals)
                p_val_float = float(p_val)
                is_normal = p_val_float > 0.05
                note = None
            except Exception as e:
                p_val_float = None
                is_normal = False
                note = f"D'Agostino-Pearson failed: {e}"

        results[name_str] = NormalityResult(
            test_used=test_used,
            p_value=p_val_float,
            n=n,
            is_normal=is_normal,
            note=note,
        )
    return results


def compute_variance_homogeneity(
    df: pd.DataFrame, outcome_col: str, group_col: str
) -> VarianceHomogeneityResult | None:
    """Compute Levene's homogeneity of variance test robustly across all groups."""
    grouped = df.groupby(group_col)[outcome_col]
    group_arrays = [group_series.dropna().values for _, group_series in grouped]
    group_arrays = [arr for arr in group_arrays if len(arr) > 0]

    if len(group_arrays) < 2:
        return None

    if any(len(arr) < 2 for arr in group_arrays):
        return VarianceHomogeneityResult(
            test_used="Levene",
            statistic=0.0,
            p_value=0.0,
            equal_variances=False,
        )

    try:
        stat, p_val = stats.levene(*group_arrays, center="median")
        p_val_float = float(p_val)
        if np.isnan(p_val_float):
            return VarianceHomogeneityResult(
                test_used="Levene",
                statistic=0.0,
                p_value=0.0,
                equal_variances=False,
            )
        return VarianceHomogeneityResult(
            test_used="Levene",
            statistic=float(stat),
            p_value=p_val_float,
            equal_variances=p_val_float > 0.05,
        )
    except Exception:
        return VarianceHomogeneityResult(
            test_used="Levene",
            statistic=0.0,
            p_value=0.0,
            equal_variances=False,
        )


def compute_expected_cell_counts(
    df: pd.DataFrame, outcome_col: str, group_col: str
) -> tuple[list[list[float]] | None, float | None]:
    """Compute expected cell counts contingent matrix and minimum expected count."""
    clean_df = df[[group_col, outcome_col]].dropna()
    if clean_df.empty:
        return None, None

    observed = pd.crosstab(clean_df[group_col], clean_df[outcome_col]).values
    if observed.size == 0 or observed.sum() == 0:
        return None, None

    try:
        _, _, _, expected = stats.chi2_contingency(observed)
        expected_list = expected.tolist()
        min_val = float(np.min(expected))
        return expected_list, min_val
    except Exception:
        row_totals = observed.sum(axis=1, keepdims=True)
        col_totals = observed.sum(axis=0, keepdims=True)
        n = observed.sum()
        if n == 0:
            return None, None
        expected = (row_totals @ col_totals) / n
        expected_list = expected.tolist()
        min_val = float(np.min(expected))
        return expected_list, min_val


def compute_sphericity(
    df: pd.DataFrame,
    outcome_col: str,
    group_col: str,
    repeated_measures: bool,
    n_conditions: int | None,
) -> SphericityResult | None:
    """Compute Mauchly's sphericity test for repeated measures."""
    if not repeated_measures:
        return None
    if n_conditions is None or n_conditions < 3:
        return None

    clean_df = df[[group_col, outcome_col]].dropna()
    grouped = clean_df.groupby(group_col)[outcome_col]
    unique_groups = list(grouped.groups.keys())
    p = len(unique_groups)

    if p < 3:
        return SphericityResult(
            statistic=1.0,
            p_value=1.0,
            sphericity_assumed=True,
            note="Sphericity mathematically guaranteed for < 3 conditions.",
        )

    groups_data = {str(name): group_series.values for name, group_series in grouped}
    lengths = [len(arr) for arr in groups_data.values()]
    n = min(lengths) if lengths else 0

    if n <= p:
        return SphericityResult(
            statistic=0.0,
            p_value=0.0,
            sphericity_assumed=False,
            note=(f"Insufficient subjects (n={n}) relative to conditions (p={p}) to perform Mauchly's test."),
        )

    X = np.column_stack([np.asarray(arr[:n], dtype=float) for arr in groups_data.values()])
    sigma = np.cov(X, rowvar=False)

    d = p - 1
    A = np.zeros((p, p))
    A[:, 0] = 1.0
    A[:, 1:] = np.eye(p)[:, :-1]
    try:
        Q, R = np.linalg.qr(A)
        M = Q[:, 1:]
    except Exception as e:
        return SphericityResult(
            statistic=0.0,
            p_value=0.0,
            sphericity_assumed=False,
            note=f"Error constructing contrast matrix: {e}",
        )

    try:
        S = M.T @ sigma @ M
        det_S = np.linalg.det(S)
        tr_S = np.trace(S)
    except Exception as e:
        return SphericityResult(
            statistic=0.0,
            p_value=0.0,
            sphericity_assumed=False,
            note=f"Error computing transformed covariance matrix: {e}",
        )

    if tr_S <= 0:
        return SphericityResult(
            statistic=0.0,
            p_value=0.0,
            sphericity_assumed=False,
            note="Zero trace of transformed covariance matrix.",
        )

    W = det_S / ((tr_S / d) ** d)
    W = float(np.clip(W, 1e-15, 1.0))

    df_chi2 = int(p * (p - 1) / 2 - 1)
    if df_chi2 <= 0:
        df_chi2 = 1

    correction = 1.0 - (2.0 * (d**2) + d + 2.0) / (6.0 * d * (n - 1))
    chi2_val = -(n - 1) * correction * np.log(W)
    chi2_val = float(max(0.0, chi2_val))

    p_val = float(stats.chi2.sf(chi2_val, df_chi2))

    return SphericityResult(
        statistic=W,
        p_value=p_val,
        sphericity_assumed=p_val > 0.05,
        note=None,
    )


def compute_missing_summary(df: pd.DataFrame, outcome_col: str, group_col: str) -> MissingDataSummary:
    """Compute per-column missing metrics.

    Includes a missingness-vs-group association chi-square test.
    """
    n_total = len(df)

    outcome_missing_count = int(df[outcome_col].isna().sum()) if n_total > 0 else 0
    outcome_missing_pct = float(outcome_missing_count / n_total * 100) if n_total > 0 else 0.0

    group_missing_count = int(df[group_col].isna().sum()) if n_total > 0 else 0
    group_missing_pct = float(group_missing_count / n_total * 100) if n_total > 0 else 0.0

    valid_group_df = df[df[group_col].notna()]
    if valid_group_df.empty:
        association = MissingnessAssociationResult(
            test_used="Chi-Square",
            statistic=None,
            p_value=None,
            significant=None,
            note="No valid groups to check missingness association.",
        )
    else:
        missing_mask = valid_group_df[outcome_col].isna()
        contingency = pd.crosstab(valid_group_df[group_col], missing_mask)
        if contingency.shape[0] < 2 or contingency.shape[1] < 2:
            association = MissingnessAssociationResult(
                test_used="Chi-Square",
                statistic=None,
                p_value=None,
                significant=None,
                note=("No missing values (or all missing values) to calculate association."),
            )
        else:
            try:
                chi2, p_val, _, _ = stats.chi2_contingency(contingency.values)
                association = MissingnessAssociationResult(
                    test_used="Chi-Square",
                    statistic=float(chi2),
                    p_value=float(p_val),
                    significant=float(p_val) < 0.05,
                    note=None,
                )
            except Exception as e:
                association = MissingnessAssociationResult(
                    test_used="Chi-Square",
                    statistic=None,
                    p_value=None,
                    significant=None,
                    note=f"Association test failed: {e}",
                )

    return MissingDataSummary(
        outcome_missing=MissingColumnSummary(count=outcome_missing_count, percentage=outcome_missing_pct),
        group_missing=MissingColumnSummary(count=group_missing_count, percentage=group_missing_pct),
        association=association,
    )


def compute_outliers(df: pd.DataFrame, outcome_col: str, group_col: str) -> dict[str, OutlierSummary]:
    """Compute outliers per group using IQR rule."""
    results = {}
    grouped = df.groupby(group_col)
    for name, group_df in grouped:
        name_str = str(name)
        group_series = group_df[outcome_col].dropna()
        if len(group_series) < 4:
            results[name_str] = OutlierSummary(count=0, indices=[])
            continue
        q1 = group_series.quantile(0.25)
        q3 = group_series.quantile(0.75)
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        outliers_mask = (group_series < lower_bound) | (group_series > upper_bound)
        outliers_series = group_series[outliers_mask]
        results[name_str] = OutlierSummary(
            count=len(outliers_series),
            indices=outliers_series.index.tolist(),
        )
    return results


def compute_data_properties(
    df: pd.DataFrame,
    outcome_col: str,
    group_col: str,
    repeated_measures: bool = False,
    n_conditions: int | None = None,
) -> DataProperties:
    """Compute properties of the data to evaluate statistical test applicability.

    Args:
        df: The dataset DataFrame.
        outcome_col: Column name representing the values (dependent variable).
        group_col: Column name representing the groups (independent variable).
        repeated_measures: Set True if repeated-measures design.
        n_conditions: Minimum number of conditions for repeated measures.

    Returns:
        A DataProperties object.

    Raises:
        ValueError: If columns are missing or DataFrame is empty.
    """
    if df.empty:
        raise ValueError("DataFrame is empty.")
    if group_col not in df.columns:
        raise ValueError(f"Group column {group_col!r} not found in DataFrame.")
    if outcome_col not in df.columns:
        raise ValueError(f"Value column {outcome_col!r} not found in DataFrame.")

    # Drop missing groups/outcomes for grouping purposes
    clean_df = df[[group_col, outcome_col]].dropna()

    # Exclude groups with zero rows after filtering
    grouped = clean_df.groupby(group_col)[outcome_col]
    group_sizes = {str(k): len(v) for k, v in grouped if len(v) > 0}
    n_groups = len(group_sizes)

    # Determine outcome type guess
    outcome_type = guess_outcome_type(df[outcome_col])

    # Sample if dataset is too large (> 50,000 rows) for performance
    sampled = False
    if len(df) > 50000:
        df_sampled = df.sample(n=50000, random_state=42)
        sampled = True
    else:
        df_sampled = df

    # Sub-computations
    if outcome_type == "continuous":
        normality = compute_normality(df_sampled, outcome_col, group_col)
        all_groups_normal = all(g.is_normal for g in normality.values()) if normality else False
        variance_homogeneity = compute_variance_homogeneity(df_sampled, outcome_col, group_col)
        expected_cell_counts = None
        min_expected_cell_count = None
    else:
        normality = {}
        all_groups_normal = False
        variance_homogeneity = None
        expected_cell_counts, min_expected_cell_count = compute_expected_cell_counts(df, outcome_col, group_col)

    # Sphericity check
    sphericity = compute_sphericity(df, outcome_col, group_col, repeated_measures, n_conditions)

    # Missing values summary
    missing = compute_missing_summary(df, outcome_col, group_col)

    # Outliers
    outliers = compute_outliers(df_sampled, outcome_col, group_col) if outcome_type == "continuous" else {}

    # Warning for sample size
    small_groups = [g for g, size in group_sizes.items() if size < 5]
    if small_groups:
        sample_size_warning = (
            f"Warning: The following groups have small sample sizes (n < 5): {', '.join(small_groups)}."
        )
    else:
        sample_size_warning = None

    return DataProperties(
        outcome_type_guess=outcome_type,
        n_groups=n_groups,
        group_sizes=group_sizes,
        normality=normality,
        all_groups_normal=all_groups_normal,
        variance_homogeneity=variance_homogeneity,
        expected_cell_counts=expected_cell_counts,
        min_expected_cell_count=min_expected_cell_count,
        sphericity=sphericity,
        missing=missing,
        outliers=outliers,
        sample_size_warning=sample_size_warning,
        sampled=sampled,
    )


def compute_data_properties_for_columns(
    df: pd.DataFrame,
    group_col: str,
    value_columns: list[str],
    repeated_measures: bool = False,
    n_conditions: int | None = None,
) -> dict[str, DataProperties]:
    """Compute data properties for multiple numeric value columns.

    Args:
        df: The dataset DataFrame.
        group_col: Column name representing the groups.
        value_columns: List of columns to compute properties for.
        repeated_measures: Whether repeated measures are requested.
        n_conditions: Number of conditions for repeated measures.

    Returns:
        A mapping from column name to its computed DataProperties.
    """
    return {
        value_col: compute_data_properties(
            df,
            outcome_col=value_col,
            group_col=group_col,
            repeated_measures=repeated_measures,
            n_conditions=n_conditions,
        )
        for value_col in value_columns
    }
