# Agent Task: Implement `data_properties` Auto-Computation Module

## Context

This module computes statistical properties of a dataset
**automatically**, with no user input, whenever a dataset and grouping
column are selected or re-selected, and again after any filter is applied.
Its output is consumed by downstream logic that decides which statistical
methods are applicable for a given group/outcome combination — it must be
deterministic, pure, and fast enough to re-run on every filter change.

Before writing any code: inspect the existing codebase (project structure,
existing modules for datasets/filters/statistical methods, naming
conventions, typing/testing patterns already in use) and place this module
where it fits that structure. If a module with this responsibility already
exists, extend/refactor it rather than creating a duplicate. Match the
project's existing conventions for module layout, exports, and test
organization rather than inventing new ones.

Do **not** implement anything that requires user judgment (paired vs
independent, ordinal vs nominal, outcome vs predictor column, alpha,
covariate selection, missing-data handling strategy). Those are out of
scope for this module — see "Explicitly Out of Scope" below.

## Required Output Contract

Define a structured, typed result object (e.g. a Pydantic model, dataclass,
or whatever typed-data convention the existing codebase already uses) and a
single entry-point function — naming should follow existing project
conventions, e.g. `compute_data_properties(df, outcome_col, group_col,
repeated_measures=False, n_conditions=None) -> DataProperties`. All
sub-computations should be separate, independently testable functions
composed by this entry point (SRP).

The result object should expose at minimum these fields (adapt naming/
nesting to match existing conventions in the codebase, but keep the
semantics):

- `outcome_type_guess`: one of continuous / categorical_nominal /
  categorical_ordinal_unclear
- `n_groups`, `group_sizes`: counts per group
- `normality`: per-group result (test used, p-value, n, is_normal flag)
- `all_groups_normal`: bool
- `variance_homogeneity`: result of a homogeneity-of-variance test, or
  absent/None if outcome is categorical
- `expected_cell_counts` / `min_expected_cell_count`: for categorical
  outcomes, or absent/None if outcome is continuous
- `sphericity`: only populated if repeated-measures with 3+ conditions is
  explicitly requested by the caller
- `missing`: missing-data summary, including a simple missingness-vs-group
  association check
- `outliers`: per-group outlier summary (IQR-based)
- `sample_size_warning`: human-readable warning string, or None

Each sub-result (normality, variance homogeneity, etc.) should itself be a
typed structure with explicit named fields — avoid raw dicts for anything
consumed downstream.

## Computations to Implement

1. **`outcome_type_guess`**
   - Numeric dtype with >10 unique values → `"continuous"`.
   - Numeric or string dtype with ≤10 unique values → `"categorical_nominal"`
     by default. If dtype is integer with a small contiguous range (e.g.
     1–5, 1–7 — Likert-like), return `"categorical_ordinal_unclear"`
     instead, so the wizard can flag it to the user for confirmation rather
     than silently picking nominal or ordinal.
   - This is a **guess**, not a final answer — the field name makes that
     explicit. The wizard layer (not this module) presents it to the user
     as an editable default.

2. **`n_groups` / `group_sizes`**
   - Unique non-null values of `group_col`, with row counts. Exclude groups
     with zero rows after filtering.

3. **`normality`** (only if outcome is continuous)
   - Per group: Shapiro-Wilk if `n <= 5000`, else D'Agostino-Pearson.
   - If `n < 3` in a group, skip the test and set `is_normal = False` with
     a note — do not call scipy on insufficient data.
   - `all_groups_normal = all(g.is_normal for g in normality)`.

4. **`variance_homogeneity`** (only if outcome is continuous and
   `n_groups >= 2`)
   - Levene's test (median-centered, robust to non-normality) across all
     groups. Store statistic, p-value, and a boolean `equal_variances`.

5. **`expected_cell_counts` / `min_expected_cell_count`** (only if outcome
   is categorical)
   - Build the contingency table (group × outcome category), compute
     expected counts under independence (`row_total * col_total / N`).
   - Surface the minimum expected cell count — this is what downstream
     logic uses to choose chi-square vs Fisher's exact.

6. **`sphericity`**
   - Implement Mauchly's test but gate it behind an explicit
     `repeated_measures: bool` and `n_conditions >= 3` argument passed into
     `compute_data_properties` — do not attempt to infer repeated-measures
     structure from the data (that's a user decision, out of scope here).
     If the flag isn't set, leave this field `None`.

7. **`missing`**
   - Per-column missing count/percentage for `outcome_col` and
     `group_col`.
   - A simple association check between missingness in `outcome_col` and
     group membership (e.g. chi-square of missing-vs-present across
     groups) — informational only, do not act on it.

8. **`outliers`**
   - IQR method (1.5×IQR beyond Q1/Q3) per group, for continuous outcomes
     only. Report count and indices/row identifiers, not a decision to
     remove them.

9. **`sample_size_warning`**
   - If any group has `n < 5`, populate a human-readable warning string.
     Don't block computation — just flag it.

## Engineering Rules

- **Pure functions, no side effects.** This module must not read files,
  hit a session store, or depend on any web-framework request/response
  objects. Input is a dataframe (or equivalent) + column names + the
  explicit repeated-measures flags; output is the typed result object.
  This makes it trivially unit-testable and reusable outside any wizard/
  API context.
- **One function per computation** (e.g. `compute_normality`,
  `compute_variance_homogeneity`, `compute_expected_cell_counts`,
  `compute_missing_summary`, `compute_outliers`, `guess_outcome_type`),
  composed by the entry point. No god-function.
- **Never raise on insufficient data** — degrade gracefully (e.g. skip a
  test, set fields to None/absent, add a warning) rather than throwing,
  since this runs automatically and must not break the surrounding flow
  mid-session. Exception: invalid input (missing columns, empty dataset)
  should raise a clear, typed exception that callers can catch and map to
  an appropriate error response.
- **No hardcoded alpha outside this module's internal `is_normal`/
  `equal_variances` flags.** Downstream significance decisions belong to
  user-facing method-selection logic, not here.
- **Performance**: must be safe to call on every filter change. Avoid
  O(n²) operations; use vectorized statistical/numerical library calls. If
  a dataset exceeds a configurable row threshold (e.g. 50,000 rows),
  sample for the normality/outlier checks rather than computing on the
  full set, and note this in the result (e.g. a `sampled: bool` flag).
- **Typing**: follow whatever strict-typing standard the project already
  enforces (e.g. mypy --strict equivalent). No untyped public signatures.
- **Library choice**: use the project's existing statistics library
  (e.g. `scipy.stats` if already a dependency, or an equivalent already in
  use) for all statistical tests — do not hand-roll statistical test
  implementations, and do not introduce a new statistics dependency if a
  suitable one is already present in the project.

## Explicitly Out of Scope (do not implement here)

- Choosing outcome vs grouping column (user input, passed in as args).
- Paired/independent determination (passed in as args if needed later).
- Ordinal vs nominal final classification (this module only flags
  ambiguous cases; final call is a user decision made elsewhere).
- Alpha/significance threshold selection for actual hypothesis testing.
- Covariate selection.
- Missing-data remediation (imputation, deletion) — report only.
- Outlier removal — report only.
- Calling any statistical-method-applicability or method-selection
  logic — that consumes this module's output but lives elsewhere.

## Testing Requirements

- Unit test each computation function in isolation with constructed
  fixtures: normal data, skewed data, tiny groups (n<3), groups with
  unequal variance, balanced/unbalanced contingency tables, sparse cells
  (<5 expected count), data with missing values, data with known outliers.
- Test the outcome-type guess against: continuous numeric, binary numeric,
  small-integer Likert-like, string categorical, high-cardinality string
  (should still resolve to categorical_nominal, not crash).
- Test graceful degradation: empty group, n=1 group, n=2 group (below the
  minimum sample size needed for the normality test in use).
- Test that the entry point raises on missing columns/empty dataset, and
  degrades (not raises) on small-but-valid data.
- Match the project's existing test coverage gate/threshold for this
  module; if none is established yet, target >90%.

## Deliverable

A self-contained module (file or small package, placed according to the
project's existing structure — see "Context" above) plus a corresponding
test module following the project's existing test layout and naming
conventions. Update any package `__init__`/export files as needed to match
existing patterns. Do not modify unrelated routing, method-selection,
filter, plot, or export code as part of this task — this is a
self-contained, isolated module.
