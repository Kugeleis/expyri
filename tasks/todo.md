# ExPyRi 0.9.5 → 1.0 Task List

Plan: [plan.md](./plan.md) · Intent: [../docs/intent/expyri.md](../docs/intent/expyri.md)

## Phase 1: Correctness core

### Task 1: Fix method display-name mappings in templates

**Status:** Method-label implementation committed as `d8d05b3` on 2026-10-18. That commit left `task check` failing; the fixture correction and a direct passing aggregate run are recorded below. Narrow-viewport work is explicitly out of scope.

**Description:** Give every statistical method one plugin-owned, human-readable label and use it consistently in selection, results, and plot annotations. Preserve machine IDs, existing plugin compatibility, statistical behavior, and API/export schemas. The detailed contract, label table, rationale, and risks are in [plan.md](./plan.md#task-1-implementation-plan-consistent-method-display-names).

**Acceptance criteria:**
- [x] A non-abstract `StatMethod.display_name` property supplies a simple fallback; all eleven built-ins provide explicit labels, without a central hard-coded mapping.
- [x] Steps 3, 4, and 5 use those labels for continuous, categorical, hierarchical, and custom methods; unknown result IDs remain readable and HTML-escaped, and obsolete GMM wording is removed.
- [x] Registry/form/session/result IDs, sorting and applicability behavior, and API/export payloads remain unchanged; focused tests, browser checks, and final quality gates pass (see verification record for the permanent fixture correction and direct aggregate rerun).

**Dependencies:** None outside Task 1. **Total scope:** 18 implementation/test/README files, split into the small steps below; not the original four-to-five-file estimate. Do not start Tasks 2–10.

#### Step 1.1: Define the backward-compatible label contract

**Description:** First add focused regression tests, then add a concrete, read-only `display_name` property to the base class. Default to `self.name.replace("_", " ").title()`. Document the optional override in the existing plugin recipe; do not require existing plugins to change.

**Acceptance criteria:**
- [x] An otherwise valid legacy subclass instantiates unchanged and gets a nonempty deterministic fallback (for example, `legacy_stat` → `Legacy Stat`).
- [x] A custom subclass can override the label without changing its machine `name` or zero-argument registration contract.
- [x] README explains friendly display labels versus stable registry/result IDs, with no new constructor argument, abstract method, or dependency.

**Verification:** Record red then green for `uv run pytest tests/unit/test_stats_display_names.py tests/unit/test_extensibility.py`.

**Dependencies:** None.

**Files likely touched:** [base.py](../app/stats/base.py), new `tests/unit/test_stats_display_names.py`, [README.md](../README.md).

**Estimated scope:** Medium — 3 files.

#### Step 1.2: Label the two independent two-group methods

**Description:** Add explicit property overrides to the independent t-test and Mann-Whitney plugins. Add exact label expectations to the new unit-test module before implementation.

**Acceptance criteria:**
- [x] `ttest_ind` displays **Independent two-sample t-test**, and `mann_whitney` displays **Mann-Whitney U test**.
- [x] Registry keys and `name` values remain unchanged; calculations, applicability, and result summaries are unchanged.

**Verification:** `uv run pytest tests/unit/test_stats_display_names.py tests/unit/test_stats_methods.py -k 'display_name or ttest or mann_whitney'`.

**Dependencies:** Step 1.1.

**Files likely touched:** [ttest.py](../app/stats/builtin/ttest.py), [mann_whitney.py](../app/stats/builtin/mann_whitney.py), `tests/unit/test_stats_display_names.py`.

**Estimated scope:** Medium — 3 files.

#### Step 1.3: Label the remaining flat methods

**Description:** Add explicit labels to flat ANOVA, Kruskal-Wallis, and chi-square, with parameterized unit expectations from the label table.

**Acceptance criteria:**
- [x] The three plugins return the exact labels in [plan.md](./plan.md#proposed-built-in-labels), preserving ANOVA capitalization and correct test names.
- [x] Their IDs, result payloads, descriptions, applicability, and numerical behavior remain unchanged.

**Verification:** `uv run pytest tests/unit/test_stats_display_names.py tests/unit/test_stats_methods.py`.

**Dependencies:** Step 1.1; execute after Step 1.2 to avoid concurrent edits to the shared unit-test file.

**Files likely touched:** [anova.py](../app/stats/builtin/anova.py), [kruskal_wallis.py](../app/stats/builtin/kruskal_wallis.py), [chi_square.py](../app/stats/builtin/chi_square.py), `tests/unit/test_stats_display_names.py`.

**Estimated scope:** Medium — 4 files.

#### Checkpoint A: Contract and flat metadata

- [x] Steps 1.1–1.3 are green; old custom plugins still instantiate and register.
- [x] Checkpoint diff contains only label metadata, its tests, and the plugin-documentation addition; no changed formulas, registry IDs, or API/result schemas.
- [x] Continued to hierarchical labels only after this checkpoint passed.

#### Step 1.4: Label all hierarchical methods

**Description:** Add labels for the six existing hierarchical methods in their four modules, including diagnostics. Extend the same focused unit tests; do not refactor or run additional statistical calculations to determine a label.

**Acceptance criteria:**
- [x] All six hierarchical labels match [plan.md](./plan.md#proposed-built-in-labels), distinguishing cluster means, corrected proportions, LMM, and diagnostics.
- [x] An explicit parameterized test covers all eleven built-ins and verifies their stable IDs without assuming a fixed global registry size.
- [x] Properties have no side effects and introduce no changes to hierarchy eligibility, flags, test execution, or result serialization.

**Verification:** `uv run pytest tests/unit/test_stats_display_names.py tests/unit/test_hierarchical_stats.py tests/unit/test_extensibility.py`.

**Dependencies:** Step 1.1; execute after Step 1.3 because the unit-test module is shared.

**Files likely touched:** [hierarchical/anova.py](../app/stats/builtin/hierarchical/anova.py), [hierarchical/kruskal_wallis.py](../app/stats/builtin/hierarchical/kruskal_wallis.py), [hierarchical/lmm.py](../app/stats/builtin/hierarchical/lmm.py), [hierarchical/diagnostic.py](../app/stats/builtin/hierarchical/diagnostic.py), `tests/unit/test_stats_display_names.py`.

**Estimated scope:** Medium — 5 files.

#### Step 1.5: Wire labels through the complete wizard presentation

**Description:** Add regression tests before changing the shared renderer and three templates. Use one registry snapshot for the existing method lists and a derived `method_display_names` context dictionary. Selection reads `method.display_name`; stored-result consumers read the map using `.get(method_name, method_name)`. Do not persist presentation fields or create another helper/service abstraction.

**Acceptance criteria:**
- [x] Steps 3, 4, and 5 render the same labels for built-in and custom plugins (with overrides and fallback); no ID-to-label `if`/`elif` chains remain. Existing help headings use the same label source, and the nonexistent hierarchical-regression/GMM label is corrected.
- [x] Full-page and HTMX responses handle registered and unknown historical IDs without errors, autoescape label text, and never mutate the stored result dictionaries or their ordering.
- [x] Continuous/discrete radio values, checked/disabled state, applicability-first ordering, method-key sorting, route responses, and numerical result fields retain existing behavior. Tests isolate and restore temporary registry/session state.

**Verification:** `uv run pytest tests/integration/test_method_display_names.py tests/integration/test_wizard_flow_htmx.py tests/unit/test_router_helpers.py tests/unit/test_extensibility.py`.

**Test coverage details:** Parameterize built-in label rendering without executing every statistical method. Include a deterministic normal two-group HTTP/HTMX flow and a categorical selection; seed representative hierarchical results to check their display. Assert the map is keyed by registry IDs, the three visible surfaces agree, raw form/API IDs remain unchanged, and an unknown ID/label containing HTML metacharacters is escaped. Cover empty results and unchanged sorting through existing tests. Do not expand the already over-300-line HTMX test module.

**Dependencies:** Steps 1.2, 1.3, and 1.4.

**Files likely touched:** [dependencies.py](../app/wizard/router/dependencies.py), [step_3.html](../app/templates/partials/step_3.html), [step_4.html](../app/templates/partials/step_4.html), [step_5.html](../app/templates/partials/step_5.html), new `tests/integration/test_method_display_names.py`.

**Estimated scope:** Medium — 5 files.

#### Step 1.6: Update the browser regression expectations

**Description:** Update the existing Playwright flows rather than creating another server fixture or browser toolchain. The full-flow test currently asserts that the results table contains the raw `ttest_ind` ID; replace that text expectation with the friendly label while retaining key-based input selectors. Extend the visualization-card assertions to cover the same label on plots.

**Acceptance criteria:**
- [x] The full wizard flow verifies a friendly selection/result label while submitting `ttest_ind` unchanged, then reaches Export successfully.
- [x] The visualization-card flow generates plots and verifies **Independent two-sample t-test** in plot metadata, consistent with the selection/results label.
- [x] No sleeps, skipped tests, weakened assertions, browser harness changes, or new dependencies are introduced to make the checks pass.

**Verification:** `uv run pytest tests/e2e/test_playwright_e2e.py -k 'full_wizard_flow or visualization_cards'`. A missing-browser skip is a reported blocker, not a pass; resolve the existing runtime prerequisite and rerun before declaring browser behavior verified.

**Dependencies:** Step 1.5.

**Files likely touched:** [test_playwright_e2e.py](../tests/e2e/test_playwright_e2e.py).

**Estimated scope:** Small — 1 file.

#### Checkpoint B: Complete label journey

- [x] Steps 1.4–1.6 pass: all eleven built-ins have labels; selection, results, and plot annotations agree.
- [x] Custom plugins work without core/template edits, legacy plugins still work, and unknown results remain visible without session/schema changes.
- [x] Desktop browser labels verified; owner approved proceeding to the final commit. Narrow-viewport work was explicitly excluded by the owner; no CSS or layout changes were made.

#### Step 1.7: Establish commit readiness

**Description:** Validate the finished Task 1 slice, inspect the exact diff, and prepare the owner-approved single atomic fix, including Task 1 completion updates.

**Acceptance criteria:**
- [x] Focused naming, plugin-extensibility, renderer, API compatibility, and browser checks pass, followed by a direct successful `task check` run at the unchanged 90% local coverage minimum (see follow-up correction below).
- [x] Review confirms the planned SOLID/DRY/SRP/KISS boundaries, no new dependency/schema/registry abstraction, new files under 300 lines, no unrelated reformatting, and README documentation of the optional display-name contract.
- [x] Commit scope is explicitly reviewed: Task 1 implementation, tests, README, and owner-approved planning updates; no unrelated work or release/version bump is included.

**Verification sequence:**

1. Focused regression selection: `uv run pytest tests/unit/test_stats_display_names.py tests/unit/test_stats_methods.py tests/unit/test_hierarchical_stats.py tests/unit/test_router_helpers.py tests/unit/test_extensibility.py tests/integration/test_method_display_names.py tests/integration/test_wizard_flow_htmx.py tests/e2e/test_api_e2e.py`.
2. Run the two Playwright selectors from Step 1.6 if not already verified on the final diff. Do not duplicate identical completed runs.
3. Run `task check` as the final aggregate gate (Ruff, HTML/JS checks, ty, hooks, and the suite with coverage). The command must exit successfully without temporary ignored-data repairs before declaring commit readiness. If it fails, report the failure and resolve the blocker, then rerun the exact command; do not silence failures or lower thresholds. Use the existing unit-test/task integration when available.
4. Inspect `git status --short`, `git diff --check`, `git diff`, and `git diff --cached`; include newly created implementation tests explicitly when staging. Never use `git add .`. Owner approved including Task 1 status updates and the two pre-existing minor planning edits; leave the intent and repository-guidance documents unchanged.
5. Commit only when requested, with subject `fix: centralize statistical method display names` and trailer `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`. Mark Task 1 complete only after verification, not when the plan is saved.

**Dependencies:** Checkpoints A and B, which cover Steps 1.1–1.6.

**Files likely touched:** Checklist status in [plan.md](./plan.md) and [todo.md](./todo.md) only; no additional implementation.

**Estimated scope:** Small — validation and commit preparation.

#### Verification record — 2026-10-18

- TDD: contract tests failed before the base property (3 failures); explicit two-group labels (2), remaining flat labels (3), hierarchical labels (6), and each HTTP/HTMX presentation surface failed before their fixes. All corresponding focused selections subsequently passed.
- Focused final regression selection: **142 passed**. The two affected Playwright flows passed after the owner-approved installation of missing Chromium; no browser harness or skip behavior was changed.
- Review mutation: temporarily keyed the label map by plugin `name` instead of registry key; both alias-result tests failed. Restored registry-keyed lookup before final validation.
- `task check`: Ruff, formatting, ESLint, Prettier, ty, and all hooks passed. Its suite reported **280 passed / 2 setup errors** because an existing flights-browser fixture expects ignored `data/nycflights.csv`, while the sample is tracked at `test_data/nycflights.csv`.
- The initial workaround temporarily copied that tracked sample into the expected runtime path and reran the unchanged complete coverage command: **282 passed**, **94.15% coverage**, no skips. The copy was then removed and the fixture source was not fixed in `d8d05b3`, leaving `task check` reproducibly failing. Treating that temporary result as commit readiness was incorrect.
- Follow-up after the owner reported the failure: reproduced the exact `task check` failure (**280 passed / 2 setup errors**), then changed the flights fixture to resolve tracked `test_data/nycflights.csv` relative to its own file. Both original failing browser tests passed (**2 passed**). The exact `task check` command then exited **0**: **282 passed**, **94.15% coverage**, no skips; lint, formatting, types, and hooks all passed. No ignored runtime dataset was present before or after the run. No tests, thresholds, dependency manifests, or task commands were weakened or changed.
- Desktop browser verification confirmed the same independent t-test label in selection, results, and generated plot metadata. An existing navigation console warning about `hx-include="#workspace-container form"` was observed when leaving Results, whose template has no form; unrelated navigation changes remain out of scope.
- Owner explicitly excluded narrow-viewport work and approved one final commit including implementation, tests, README, and Task 1 planning/status updates. Tasks 2–10 remain untouched.

### Task 2: Multiple-testing correction (Holm) for flat-mode results
**Status:** Complete on 2026-10-18. Implemented and verified in two local commits: `b3dc4c7` (service/result contract and export persistence) and `fix: use adjusted significance throughout the wizard` (consistent presentation, plot filtering, and this completion record); not pushed. Minor review findings were amended into their logical slice.

**Description:** When a user evaluates k value columns, k independent tests run with no correction — the classic multiple-comparisons misuse this tool exists to prevent. Apply Holm correction across all results of one submission, per method family (continuous / discrete). Store `p_value_adjusted` and `correction_method` on `StatResult`; render both raw and adjusted p-values in step_4 with a one-sentence legend; significance highlighting uses the adjusted value.
**Acceptance criteria:**
- [x] `StatResult` gains `p_value_adjusted: float | None` and `correction_method: str | None`
- [x] `WizardAnalysisService.submit_method` applies Holm across continuous-family results and across discrete-family results (separate families)
- [x] Single-column submissions behave identically to before (adjusted == raw, method recorded)
- [x] Step 4 table shows adjusted p-value column + legend; row highlighting keyed on adjusted p
- [x] JSON/Parquet exports include the new fields automatically
**Verification:**
- [x] New unit tests: correction math (known p-vector → expected Holm output), family separation, single-result passthrough
- [x] `uv run pytest tests/unit/test_stats_methods.py tests/integration/test_wizard_flow_basic.py` (included in the focused selections below)
- [x] `task check` green

**Verification record — 2026-10-18:**
- Owner confirmed flat-only correction, adjusted significance for highlighting/charts/automatic plot filtering, unchanged hierarchical/post-hoc calculations, and local commits without pushing.
- TDD: the initial model/service tests failed in all 10 cases before implementation; the new presentation tests recorded 5 failures before template/sort support. The browser flow exposed a new rendering regression when dataset selection resets results to `None`; a focused failing HTTP test preceded its fix.
- Service slice: **53 passed**, including known unsorted Holm vectors, ties/clamping, zero/one boundaries, separate families, single outcomes, resubmission, unchanged hierarchical/post-hoc output, JSON API/export, and Parquet metadata. Ruff, formatting, and ty passed before commit.
- Final focused selection: `uv run pytest tests/unit/test_multiple_testing.py tests/unit/test_significance.py tests/unit/test_stats_methods.py tests/unit/test_router_helpers.py tests/unit/test_parquet_metadata.py tests/unit/test_exporters.py tests/integration/test_multiple_testing.py tests/integration/test_wizard_flow_basic.py tests/integration/test_wizard_flow_htmx.py tests/integration/test_wizard_flow_mixed.py tests/e2e/test_multiple_testing_playwright.py -q --tb=short` — **74 passed**.
- Chromium verified real multi-column t-tests, raw-significant/adjusted-nonsignificant rows, adjusted sorting, live threshold changes, and generation of only the adjusted-significant plot; no uncaught page errors. Result-table screenshot inspected. No CSS/layout work was included.
- Mutation checks: reversing the flat-only guard caused both single-outcome cases to fail; temporarily using raw significance caused 5 consumer/highlighting tests to fail. Both mutations were restored before final validation.
- Exact `task check` exited **0**: **312 passed**, **94.23% coverage**, no skipped tests; Ruff, formatting, ESLint, Prettier, ty, and all hooks passed. No dependencies, thresholds, existing test skips, or task commands were changed. The new Chromium regression reuses the existing harness's browser-availability marker; it executed rather than skipped locally.
- Raw values/statistics/summaries and existing explicit top-N plot selection are preserved; legacy and hierarchical results use raw significance when no adjusted value exists. Tasks 3–10 remain out of scope.

**Dependencies:** None
**Files touched:** [result schema](../app/stats/models.py), [analysis service](../app/wizard/analysis_service.py), [significance policy](../app/wizard/statistics.py), [plot selection](../app/wizard/plotting.py), [renderer/chart](../app/wizard/router/dependencies.py), [sorting](../app/wizard/router/htmx_results.py), [results template](../app/templates/partials/step_4.html), [plot template](../app/templates/partials/step_5.html), [README](../README.md), three new focused [unit](../tests/unit/test_multiple_testing.py)/[significance](../tests/unit/test_significance.py)/[HTTP](../tests/integration/test_multiple_testing.py) test modules, one new [Chromium regression](../tests/e2e/test_multiple_testing_playwright.py), and existing [API flow](../tests/integration/test_wizard_flow_basic.py), [JSON exporter](../tests/unit/test_exporters.py), and [Parquet](../tests/unit/test_parquet_metadata.py) tests.
**Scope:** 16 implementation/test/README files plus this completion record, delivered in two verified code slices.

### Task 3: Chi-square expected-count guard + Fisher exact fallback
**Description:** `min_expected_cell_count` is computed but never enforced; chi-square runs on tables with tiny expected counts (invalid approximation). Enforce min expected ≥ 5 in `ChiSquare.is_applicable`, and add a `fisher_exact` builtin plugin for 2×2 tables with small counts so users always have a valid option. Update the step-3 info-callout to explain both.
**Acceptance criteria:**
- [ ] `ChiSquare.is_applicable` returns False when `min_expected_cell_count` < 5
- [ ] New `fisher_exact` plugin registered, applicable for 2×2 categorical tables (any expected counts; required when counts are small), reports odds ratio as effect size
- [ ] Plugin package imports it so startup registration works
- [ ] Step-3 info-callout documents the expected-count rule and Fisher fallback
**Verification:**
- [ ] Unit tests: chi-square inapplicable with small expected counts; fisher_exact applicable + correct result on a known 2×2 table
- [ ] `uv run pytest tests/unit/test_stats_methods.py tests/unit/test_extensibility.py`
- [ ] `task check` green
**Dependencies:** None
**Files likely touched:** `app/stats/builtin/chi_square.py`, `app/stats/builtin/fisher_exact.py` (new), `app/stats/builtin/__init__.py`, `app/templates/partials/step_3.html`, `tests/unit/test_stats_methods.py`
**Estimated scope:** Medium

### Task 4: Surface assumption checks in wizard UI
**Description:** Normality per group, Levene, sample-size warnings, missing-data association, and outliers are computed into `DataProperties` but never shown. The user sees methods disabled with no data-specific explanation. Add a collapsible assumptions panel to step 3 (and results context in step 4) rendering the per-column properties: which assumption failed, with test name, statistic, and p-value.
**Acceptance criteria:**
- [ ] Step 3 renders a collapsible per-column assumptions panel (normality per group, variance homogeneity, sample-size warning, missing-data summary)
- [ ] Panel uses the existing `compute_properties_for_columns` results already available to the route — no new computation path
- [ ] JSON method-listing route exposes the same properties (API clients get the guardrail rationale)
- [ ] Panel styling follows existing `info-callout` pattern
**Verification:**
- [ ] Integration test: step-3 response contains assumption values for a fixture dataset
- [ ] `uv run pytest tests/integration/test_wizard_flow_htmx.py tests/integration/test_wizard_flow_basic.py`
- [ ] `task check` green
**Dependencies:** Task 1 (template cleanup first to avoid rework)
**Files likely touched:** `app/wizard/router/htmx_results.py` (or the route rendering step 3), `app/templates/partials/step_3.html`, possibly a new partial `assumptions_panel.html`, `tests/integration/test_wizard_flow_htmx.py`
**Estimated scope:** Medium

### Task 5: Plain-language interpretation of results
**Description:** The results table shows bare numbers; `StatResult.summary` isn't even rendered. Non-expert users need a verdict. Add a pure helper module `app/stats/interpretation.py` producing (a) a verdict sentence per result (significant/not, adjusted-p aware, method-specific wording) and (b) an effect-size magnitude label (e.g. Cohen's d: small/medium/large; η²: small/medium/large; rank-biserial; Cramér's V). Render in step 4 and make it available to exporters.
**Acceptance criteria:**
- [ ] `app/stats/interpretation.py` with pure, unit-tested functions: `verdict_for(result) -> str` and `effect_label(result) -> str`
- [ ] Thresholds documented per effect-size type (Cohen's conventions)
- [ ] Step 4 renders summary + verdict + effect label per result row (or expandable detail)
- [ ] Verdict wording respects adjusted p-value from Task 2
**Verification:**
- [ ] Unit tests for each effect-size type and significance branch
- [ ] `uv run pytest tests/unit/` (new test file) + `task check` green
**Dependencies:** Task 2 (adjusted p-values feed verdicts)
**Files likely touched:** `app/stats/interpretation.py` (new), `app/templates/partials/step_4.html`, `tests/unit/test_interpretation.py` (new)
**Estimated scope:** Medium

## Checkpoint: Correctness core
- [ ] `task check` green (ruff, ty, pytest, coverage ≥ 90%)
- [ ] Guardrail behavior covered by unit + integration tests
- [ ] Manual: run wizard on `test_data/hsb.csv`, verify assumptions panel, adjusted p-values, verdicts, Fisher fallback path
- [ ] Review with owner before Phase 2

## Phase 2: Follow-up correctness & report

### Task 6: Post-hoc comparisons for flat ANOVA / Kruskal-Wallis
**Description:** A significant flat-mode ANOVA/Kruskal-Wallis currently stops at "difference exists" — users will eyeball pairwise means uncorrected. Add post-hoc pairwise comparisons to the flat ANOVA (Tukey HSD via `scipy.stats.tukey_hsd`) and flat Kruskal-Wallis (Dunn z-approximation + Holm, mirroring the existing hierarchical implementation), stored in `StatResult.posthoc` which already exists and serializes correctly.
**Acceptance criteria:**
- [ ] Flat ANOVA `run()` populates `posthoc` DataFrame (pair, mean diff, p, Holm-adjusted p) when ≥ 3 groups
- [ ] Flat Kruskal-Wallis `run()` populates `posthoc` (pair, z, p, Holm-adjusted p) when ≥ 3 groups
- [ ] Post-hoc only computed when the omnibus test is significant (p ≤ 0.05); otherwise `posthoc` is None with a note in summary
- [ ] Unit tests against known pairwise results
**Verification:**
- [ ] `uv run pytest tests/unit/test_stats_methods.py`
- [ ] `task check` green
**Dependencies:** None (parallel-safe with Tasks 7–8; `posthoc` field already exists)
**Files likely touched:** `app/stats/builtin/anova.py`, `app/stats/builtin/kruskal_wallis.py`, `tests/unit/test_stats_methods.py`
**Estimated scope:** Medium

### Task 7: PDF report overhaul with report-context builder
**Description:** The current PDF is title + row counts + stat numbers + plots — insufficient for "further discussion with a statistician." Build a shared report-context module that assembles: session provenance (dataset, group column, filters applied, excluded clusters), selected methods with applicability rationale, assumption-check results, per-column results with interpretation (Task 5) and adjusted p-values (Task 2), post-hoc tables (Task 6), ICC/power where present, and generation date + ExPyRi version. The PDF exporter renders this structured context.
**Acceptance criteria:**
- [ ] New module (e.g. `app/exporters/report_context.py`) builds the context from session + results; pure and unit-testable
- [ ] PDF contains: provenance section, methods + rationale, assumptions, results table with raw + adjusted p + effect labels + verdicts, post-hoc tables, plots, date/version footer
- [ ] `pdf_exporter.py` stays under 300 lines
- [ ] ReportLab tables used for results/post-hoc (readable, not paragraph soup)
**Verification:**
- [ ] Unit test: context builder output structure for a fixture session
- [ ] Integration test: PDF export returns non-empty PDF containing key section strings (via `pdftotext` or report inspection)
- [ ] `uv run pytest tests/unit/test_exporters.py tests/integration/` + `task check` green
**Dependencies:** Tasks 2, 5, 6 (consumes their outputs)
**Files likely touched:** `app/exporters/report_context.py` (new), `app/exporters/builtin/pdf_exporter.py`, `tests/unit/test_exporters.py`
**Estimated scope:** Medium

### Task 8: Render post-hoc tables and flags in results UI
**Description:** `StatResult.posthoc` and `StatResult.flags` are populated by hierarchical plugins but never rendered — dead data. Render post-hoc tables (expandable per result row) and flag badges (e.g. `OUTLIER_CLUSTER:...`, `LMM_FIT_FAILED`) in step 4.
**Acceptance criteria:**
- [ ] Step 4 renders post-hoc table per result when present (pair, estimate, p, adjusted p)
- [ ] Flags render as visible warning badges with human-readable text (map flag codes to sentences)
- [ ] Hierarchical flow integration test asserts post-hoc rows appear in the HTML
**Verification:**
- [ ] `uv run pytest tests/integration/test_hierarchical_flow.py tests/integration/test_wizard_flow_hierarchy.py`
- [ ] `task check` green
**Dependencies:** Task 6 (flat post-hoc lands in the same UI element)
**Files likely touched:** `app/templates/partials/step_4.html`, possibly `app/wizard/router/htmx_results.py`, `tests/integration/test_wizard_flow_hierarchy.py`
**Estimated scope:** Small

## Checkpoint: Report readiness
- [ ] `task check` green
- [ ] Full wizard flow on `hsb.csv` and a hierarchical fixture produces a PDF a statistician can audit
- [ ] Review with owner before Phase 3

## Phase 3: Hardening toward 1.0

### Task 9: Welch's ANOVA plugin *(pending scope confirmation — see plan Open Questions)*
**Description:** When data is normal but heteroscedastic with > 2 groups, the only current option is Kruskal-Wallis, which tests a different hypothesis (distribution equality, not means). Add a Welch's ANOVA builtin (via `scipy.stats.alexandergovern` or statsmodels) applicable when normality holds but Levene fails, with an appropriate effect size.
**Acceptance criteria:**
- [ ] `welch_anova` plugin registered; applicable: ≥ 3 groups (or > 2), all normal, Levene fails
- [ ] Effect size reported (e.g. ω² or ε² adapted); summary explains why it was recommended over classical ANOVA
- [ ] Step-3 info-callout updated
**Verification:**
- [ ] Unit tests: applicability matrix + known-result comparison
- [ ] `task check` green
**Dependencies:** Task 1 (display names)
**Files likely touched:** `app/stats/builtin/welch_anova.py` (new), `app/stats/builtin/__init__.py`, `app/templates/partials/step_3.html`, `tests/unit/test_stats_methods.py`
**Estimated scope:** Small–Medium

### Task 10: Guardrail end-to-end test + docs update
**Description:** Add an end-to-end integration test that walks the full wizard on a fixture exercising the guardrails: small-expected-count chi-square → Fisher offered; many-column submission → Holm-adjusted p-values present; heteroscedastic data → Welch offered (if Task 9 in). Update README/docs to document the guardrail behavior (multiple-testing policy, expected-count rule, interpretation labels) so the 1.0 behavior is user-visible.
**Acceptance criteria:**
- [ ] Integration test covers the guardrail paths end-to-end (JSON and/or HTMX flow)
- [ ] README "statistical behavior" section documents correction policy, applicability rules, and report contents
- [ ] Docs build passes (`task docs:build`)
**Verification:**
- [ ] `uv run pytest tests/integration/`
- [ ] `task check` + `task docs:build` green
**Dependencies:** Tasks 2, 3, 5, 6, 7 (9 optional)
**Files likely touched:** `tests/integration/test_guardrails_e2e.py` (new), `README.md`, `docs/`
**Estimated scope:** Medium

## Checkpoint: 1.0 readiness
- [ ] All acceptance criteria met; coverage ≥ 90%
- [ ] Docs reflect new guardrails
- [ ] Owner sign-off → version bump to 1.0.0
