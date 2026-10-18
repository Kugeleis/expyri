# Implementation Plan: ExPyRi 0.9.5 → 1.0 (Trustworthiness & Report Quality)

## Overview

ExPyRi's confirmed intent ([docs/intent/expyri.md](../docs/intent/expyri.md)) is: guided statistics for educated professionals with basic stats knowledge, on real grouped experiment data, where **correctness is the binding constraint** and a **fine report for further discussion** is the second focus. The current implementation has strong foundations (applicability guards, thorough assumption computation, hierarchical mode with ICC/power/post-hoc, 137 passing unit tests) but has correctness gaps that directly violate the intent, and the report is too thin for "further discussion with a statistician."

This plan closes those gaps. It is explicitly **not** a feature-count plan — every task either prevents a statistical misuse or makes the result verifiable/reportable.

## Gap Analysis (implementation vs. intent)

| # | Gap | Severity (vs. intent) |
|---|-----|----------------------|
| 1 | **No multiple-testing correction in flat mode.** Users select many value columns; each gets a raw p-value; UI highlights p ≤ 0.05 and sorts by p. With k columns, ~k·0.05 false positives expected. Hierarchical post-hoc uses Holm, but the primary flat flow has nothing. | Critical — the exact misuse the tool exists to prevent |
| 2 | **Chi-square guard ignores expected cell counts.** `min_expected_cell_count` is computed into `DataProperties` but `ChiSquare.is_applicable` never checks it; the test runs with tiny expected counts. No Fisher exact fallback. | Critical — known misuse path |
| 3 | **Computed assumptions are invisible.** Normality per group, Levene, sample-size warnings, missing-data association, outliers are all computed but never rendered in the UI. The user sees methods disabled without knowing why *for their data*. | High — guardrails without explanation don't teach |
| 4 | **No plain-language verdict.** Results table shows bare numbers; `StatResult.summary` (which contains the human-readable sentence) is not rendered in the UI. No effect-size magnitude labels for non-experts. | High |
| 5 | **No post-hoc in flat mode.** A significant 3+-group ANOVA/Kruskal-Wallis ends with "there is a difference somewhere" — the user will eyeball means and conclude pairwise differences uncorrected. Hierarchical mode already has Tukey/Dunn+Holm; flat mode has none. | High |
| 6 | **PDF report is thin.** Title, row/col counts, stat numbers, plots. Missing: methods rationale, assumption check results, filters/exclusions applied, post-hoc tables, ICC/power, interpretation, date/version. Not sufficient for "further discussion." | High — second focus of the intent |
| 7 | **Post-hoc tables and `flags` are never rendered** in any template (dead data in UI terms). | Medium |
| 8 | **Display-name mismatches in templates.** Templates map `"ttest"` but the registry key is `"ttest_ind"`; `"hierarchical_regression"` vs. actual hierarchical method names. Users see raw internal names. | Low — polish, but sloppy for a 1.0 |
| 9 | **Dead sphericity/repeated-measures machinery.** Mauchly's test is implemented but no method uses it; no paired tests exist. Real experiments are often paired — running independent tests on paired data is a classic misuse. | Scope question — see Open Questions |

## Architecture Decisions

- **Multiple-testing correction lives in the service layer** (`WizardAnalysisService.submit_method`), applied per method family (continuous / discrete) across all results of one submission, using Holm (consistent with the hierarchical plugins). Stored on `StatResult` as new fields (`p_value_adjusted`, `correction_method`) so UI and exporters render it without recomputation.
- **Significance display uses adjusted p-values** once correction exists; raw p-values remain visible for transparency. Default α stays 0.05 (existing `plots_sig_filter`).
- **Chi-square strictness**: `is_applicable` requires min expected cell count ≥ 5 (the conventional guardrail already computed in `DataProperties`). A new `fisher_exact` builtin plugin covers 2×2 tables with small counts, so strictness never leaves the user without a valid option.
- **Assumption surfacing reuses `compute_properties_for_columns`** — no new computation paths; the step-3/step-4 render context gains the properties map and templates render an assumptions panel. Guards stay the single source of truth.
- **Interpretation is a pure helper module** (`app/stats/interpretation.py`): (method, p, adjusted p, effect size, n groups) → verdict sentence + effect-magnitude label. Pure functions, fully unit-testable, consumed by UI and PDF alike.
- **Flat-mode post-hoc reuses the existing manual Dunn implementation** from the hierarchical Kruskal-Wallis plugin (z-approximation + Holm) and `scipy.stats.tukey_hsd` for ANOVA — no new dependencies.
- **PDF report gets a shared report-context builder** so the PDF (and later exporters) render from one structured object: session provenance (dataset, group column, filters, exclusions), methods + applicability rationale, assumption results, per-column results with interpretation, post-hoc tables, ICC/power. Keeps `pdf_exporter.py` under the 300-line convention.
- **No new registries or extension points** — everything rides the existing plugin architecture.

## Task 1 Implementation Plan: Consistent Method Display Names

**Status:** Proposed on 2026-10-18; implementation and commit require approval. This refines Task 1 of the existing roadmap, not a replacement plan. Tasks 2–10 remain unchanged. The authoritative execution checklist is [Task 1 in todo.md](./todo.md#task-1-fix-method-display-name-mappings-in-templates).

### Verified scope

- There are **11 built-in methods across nine plugin modules**: five flat methods and six hierarchical methods. The original estimate of four or five files was too small.
- All three method-label consumers are affected: [method selection](../app/templates/partials/step_3.html), [results](../app/templates/partials/step_4.html), and [plot annotations](../app/templates/partials/step_5.html). Direct rendering currently produces `ttest_ind` in all three.
- [StatMethod](../app/stats/base.py) has no display-name contract. Existing custom plugins must remain instantiable without adding one.
- [render_step](../app/wizard/router/dependencies.py) supplies plugin objects for selection but dictionary results for later steps. It already copies the session before sorting; label resolution must not mutate stored results.
- The existing [Playwright full-flow test](../tests/e2e/test_playwright_e2e.py) expects the raw `ttest_ind` text in the results table. That assertion must change with the UI; its radio-value selector must not change.

### Scope and non-goals

**Outcome:** A method has the same human-readable label in selection, results, and plot metadata, including custom plugins, while all machine identifiers retain their current meaning.

**Assumptions:** This is an English-label presentation fix. Labels describe the registered method, not a runtime-selected test variant. For example, the existing independent t-test plugin sometimes runs Welch's variant; that distinction stays in its existing result summary.

**Out of scope:** Statistical calculations, applicability rules, sorting semantics, new methods, API response fields, result/session schema changes, exporter changes, localization, dependency changes, unrelated refactoring, and Tasks 2–10. Updating the misleading GMM label in the existing help text is in scope; redesigning that help or its eligibility explanations is not.

### Minimal design

1. Add a **concrete, read-only** `StatMethod.display_name: str` property. Its fallback is `self.name.replace("_", " ").title()`. It is not abstract and adds no constructor argument. Built-ins override the property following the existing `name`/`description` style; custom plugins may override it but need not.
2. Each plugin owns its label. Do not add a central hard-coded ID-to-label table, a new registry, a presentation-service class, a result-model field, or template-specific naming rules.
3. In `render_step`, take one snapshot of `stat_registry.list_all()` and use it for the existing method lists and a `method_display_names: dict[str, str]` template-context map, keyed by **registry key**. This is a derived lookup, not a second source of naming definitions. Keep the public helper signature unchanged.
4. Selection renders `method.display_name` for both continuous and discrete methods. Results and plot metadata render `method_display_names.get(result.method_name, result.method_name)`. An unregistered historical/custom identifier therefore remains visible rather than causing a rendering error. No stored result is relabeled or rewritten.
5. Replace all three templates' method-ID `if`/`elif` translation chains. Use the same context labels for existing method headings in the selection help; replace the nonexistent `hierarchical_regression` / GMM terminology with the actual LMM method's label. Preserve form values, checked/disabled state, descriptions, and HTMX targets/triggers.

This keeps **SRP** (plugins own names; rendering owns presentation), **DRY** (one label definition), **OCP/LSP** (new plugins work without template edits; old subclasses still work), and **KISS** (one optional property and one context dictionary). The renderer continues to depend on the registry/base contract, not concrete plugin classes.

### Proposed built-in labels

| Stable registry/result ID | Display label |
|---|---|
| `ttest_ind` | Independent two-sample t-test |
| `mann_whitney` | Mann-Whitney U test |
| `anova` | One-way ANOVA |
| `kruskal_wallis` | Kruskal-Wallis H test |
| `chi_square` | Chi-square test of independence |
| `cluster_mean_anova` | One-way ANOVA on cluster means |
| `cluster_mean_kruskal_wallis` | Kruskal-Wallis H test on cluster means |
| `proportion_kruskal_wallis` | Kruskal-Wallis H test on corrected cluster proportions |
| `linear_mixed_model` | Linear mixed-effects model (LMM) |
| `grubbs_cluster_outlier` | Grubbs outlier test on cluster means |
| `levene_cluster_uniformity` | Levene's test of within-cluster spread |

These labels are the test expectations, not a production mapping. Do not assert that the global registry contains exactly eleven entries: extensibility tests register additional methods.

### Steps and dependencies

| Step | Deliverable | Depends on | Likely implementation files |
|---|---|---|---|
| 1.1 | Backward-compatible display-name contract, regression tests, plugin documentation | None | Base class, new focused unit test, README (3) |
| 1.2 | Labels for independent t-test and Mann-Whitney | 1.1 | Two plugins and the focused unit test (3) |
| 1.3 | Labels for flat ANOVA, Kruskal-Wallis, and chi-square | 1.1 | Three plugins and the focused unit test (4) |
| Checkpoint A | Contract/flat-plugin tests green; API identifiers unchanged | 1.1–1.3 | No additional implementation |
| 1.4 | Labels for all six hierarchical methods | 1.1 | Four hierarchical modules and the focused unit test (5) |
| 1.5 | Consistent labels through method selection, results, and plot metadata | 1.2–1.4 | Shared renderer, three templates, new focused integration test (5) |
| 1.6 | Browser regression coverage for the complete label journey | 1.5 | Existing Playwright test module (1) |
| Checkpoint B | HTTP/HTMX and real-browser behavior verified; custom plugins work | 1.4–1.6 | No additional implementation |
| 1.7 | Final quality gates, review, explicit staging boundary | Checkpoints A and B | Existing planning checklists only |

Steps 1.2–1.4 are logically independent once 1.1 is complete, but share the unit-test file: execute sequentially unless test edits are coordinated. The UI work depends on the metadata contract. No agent parallelization is needed for this small change.

### Verification and commit boundary

- Add tests before each behavior change; record the expected failure and focused passing result. Use a new `tests/unit/test_stats_display_names.py` rather than expanding the already 423-line statistical-method test module. Use a new `tests/integration/test_method_display_names.py` rather than expanding the already 306-line HTMX test module.
- Unit tests cover the inherited fallback, explicit override, all eleven expected labels, unchanged IDs, and legacy subclasses with no `display_name` implementation. Rendering tests cover all three surfaces, continuous/discrete methods, custom methods with and without overrides, an unknown historical ID, autoescaping, and unchanged persisted results/selection values. Use explicit label expectations so a template returning a raw ID cannot pass by sharing the same faulty fallback.
- Run the focused unit/integration selection first, then the two existing affected Playwright flows. Finish with **one** `task check` run, retaining the local coverage floor of at least 90%. Full commands and pass conditions are in Step 1.7. A skipped browser test is not evidence of verified browser behavior; record and resolve any missing prerequisite rather than suppressing it.
- Keep new code files under 300 lines. The renderer (323 lines) and Playwright module are already over the guideline; keep edits surgical and avoid unrelated file splitting.
- Implementation should form one atomic `fix: centralize statistical method display names` commit, including its tests and directly related README change. No version bump or new dependency is required. Do not commit during this planning task.
- Current planning documents, the intent document, and `.github/copilot-instructions.md` are untracked. Treat their staging as a separate, explicit decision: inspect `git status --short` and `git diff --cached`, stage only the Task 1 implementation paths, and never use `git add .` to sweep other work into the fix. Include the repository's required co-author trailer if a commit is later requested.

### Risks and mitigations

| Risk | Mitigation |
|---|---|
| Step 5 remains inconsistent after fixing the two originally listed templates | Include plot metadata in the same UI slice and browser assertions |
| New abstract metadata breaks external plugins | Concrete fallback plus legacy-plugin instantiation test |
| Friendly labels accidentally replace machine IDs | Preserve form values and stored/API/export `method_name`; assert them explicitly |
| Persisted results refer to an unregistered method | Raw-ID fallback for display only; no exception or session rewrite |
| A stale browser assertion breaks an otherwise working change | Update its text expectation while retaining key-based input selectors |
| Shared unit-test edits conflict | Implement metadata steps sequentially; one unit-test file is sufficient |

**Approval gate:** The plan is ready for review, not implemented or proven green. No additional product decision is required for Task 1; the roadmap's statistical open questions do not block this presentation-only fix.

## Task List

(Tracked in detail in [todo.md](./todo.md).)

### Phase 1: Correctness core
- [ ] Task 1: Fix method display-name mappings in templates (Steps 1.1–1.7 below; each implementation step touches at most five files)
- [ ] Task 2: Multiple-testing correction (Holm) for flat-mode results (M)
- [ ] Task 3: Chi-square expected-count guard + Fisher exact fallback plugin (M)
- [ ] Task 4: Surface assumption checks in wizard UI (M)
- [ ] Task 5: Plain-language interpretation of results (M)

### Checkpoint: Correctness core
- [ ] `task check` green; guardrail behavior covered by unit + integration tests

### Phase 2: Follow-up correctness & report
- [ ] Task 6: Post-hoc comparisons for flat ANOVA/Kruskal-Wallis (M)
- [ ] Task 7: PDF report overhaul with report-context builder (M)
- [ ] Task 8: Render post-hoc tables and flags in results UI (S)

### Checkpoint: Report readiness
- [ ] Full wizard flow produces a report a statistician can audit

### Phase 3: Hardening toward 1.0
- [ ] Task 9: Welch's ANOVA plugin (S–M, pending scope confirmation)
- [ ] Task 10: Guardrail end-to-end test + docs update (M)

### Checkpoint: 1.0 readiness
- [ ] All acceptance criteria met; coverage ≥ 90%; docs reflect new guardrails

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Correction changes which results look "significant" — existing users may be confused | Medium | Show raw **and** adjusted p-values; UI legend explains the correction in one sentence |
| Stricter chi-square guard disables a previously available method | Medium | Fisher exact plugin ships in the same task; info-callout updated |
| Assumptions panel clutters the wizard UI | Low | Collapsible `<details>` panel, same pattern as existing info-callout |
| PDF grows beyond 300-line file convention | Low | Report-context builder module absorbs the structure; PDF renders it |
| Template edits across tasks 2/4/5/8 conflict | Medium | Tasks are ordered sequentially; checkpoint runs the full suite between phases |

## Open Questions

- **Paired/repeated-measures designs**: in scope for 1.0, later, or never? The Mauchly sphericity code is currently dead — either a paired-test task gets added (paired t-test, repeated-measures ANOVA) or the dead code is removed. (Intent says "grouped A, B, C" which reads as between-subject; leaning *later*, but this is the owner's call.)
- **Welch's ANOVA** (Task 9): when data is normal but heteroscedastic, the current fallback is Kruskal-Wallis, which tests a different hypothesis (distributions, not means). Welch's ANOVA is the statistically better recommendation. Include?
- **Correction family definition**: one family per submission (all selected columns, per method type) is the default. Alternative: let the user pick the family. Default recommended — fewer knobs for the target user.
