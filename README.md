# ExPyRi — Experiment Evaluation Wizard

*Note: This project was formerly known as ExpYT.*

[![CI](https://github.com/Kugeleis/expyri/actions/workflows/ci.yml/badge.svg)](https://github.com/Kugeleis/expyri/actions/workflows/ci.yml)
[![Docs](https://img.shields.io/badge/docs-GitHub%20Pages-blue.svg)](https://kugeleis.github.io/expyri/)
[![CodeQL](https://github.com/Kugeleis/expyri/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/Kugeleis/expyri/actions/workflows/github-code-scanning/codeql)
[![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

ExPyRi is a modular, extensible FastAPI backend that guides users through a multi-step statistical evaluation wizard: **Dataset Selection → Preprocessing Filters → Statistical Method → Run Evaluation → Plot Selection → Report Export**.

The project is built on SOLID open/closed principles, allowing developers to add new filters, statistical methods, plots, and exporters as plugins without modifying the core API router or orchestration logic.

---

## Architecture Diagram

The wizard maintains state using an in-memory session store (interfaced via a protocol dependency, allowing easy swap to Redis/DB). Each stage is guarded by step prerequisites. Applicability guards query registries to list options suited to the dataset's current characteristics (e.g., number of groups, normality, homogeneity of variance).

```mermaid
graph TD
    subgraph Registries [Plugin Registries]
        FR["filter_registry: Registry(Filter)"]
        SR["stat_registry: Registry(StatMethod)"]
        PR["plot_registry: Registry(PlotGenerator)"]
        ER["exporter_registry: Registry(Exporter)"]
    end

    subgraph Flow [Wizard Steps]
        S1["1. Dataset Selection"] --> S1b["1b. Hierarchical Config"]
        S1b --> S2["2. Preprocessing Filters"]
        S2 --> S3["3. Statistical Method Selection"]
        S3 --> S4["4. Run Evaluation"]
        S4 --> S5["5. Plot Selection"]
        S5 --> S6["6. Report Export"]
    end

    S1b -.->|Computes Cluster Aggregates & ICC| S2
    S2 -.->|Queries & Executes| FR
    S3 -.->|Filters Applicable| SR
    S5 -.->|Filters Applicable| PR
    S6 -.->|Generates Format| ER
```

---



---

## Getting Started

### Prerequisites
- Python >= 3.12
- [uv](https://github.com/astral-sh/uv) (Python package manager)

### Installation
Clone the repository and synchronize the environment:
```bash
uv sync
```

### Running the App Locally (Development)
Start the FastAPI server with auto-reload:
```bash
task dev
```
The documentation will be available at `http://127.0.0.1:8000/docs`.

---

## UI Usage Guide

ExPyRi guides you through a step-by-step statistical evaluation wizard. Here is an extensive guide on how to use the UI, along with the statistical concepts and references underpinning each step:

### Step 1: Select Dataset & Column Mapping
1. **Upload / Select Dataset**: Upload your experiment data in `.csv`, `.xpt`, `.h5`, or `.parquet` format.
2. **Set Group Column**: Select the discrete column representing the treatment group or experimental arm.
3. **Map Metrics**: Check the continuous and discrete metric columns you wish to analyze.
4. **Hierarchical Toggle (Optional)**: If your observations are nested (e.g., measurements grouped in batches, wafers, or clusters), enable **Hierarchical Data Support**.
   - **Cluster Column (L1)**: Select the grouping variable for intermediate clusters (e.g., wafer, class, clinic).
   - **Unit Column (L0 - Optional)**: Select the column for unique unit IDs (defaults to "None" which uses the row index).
   - **Spatial Coordinates (Optional)**: Select the optional X and Y coordinate columns to enable spatial heatmap plotting.

---

### Step 2: Configure Preprocessing Filters
Add one or more filtering criteria to slice and clean the dataset before running tests:
- **Numeric Range**: Keep only observations within specified bounds.
- **Category Filter**: Include or exclude specific discrete classes.
- **Cluster Exclusion**: Exclude entire intermediate clusters (L1) from hierarchical analysis (useful for removing defective batches or outlier groups).

---

### Step 3: Statistical Method Selection
The wizard queries the backend to determine which methods are applicable based on automated tests of your filtered dataset's properties:

#### Continuous Variable Methods
- **[Independent Two-Sample t-Test](https://en.wikipedia.org/wiki/Student%27s_t-test)**: Compares means of exactly 2 groups. Requires normality and homogeneous variance.
- **[One-Way ANOVA](https://en.wikipedia.org/wiki/One-way_analysis_of_variance)**: Compares means across 3 or more groups. Requires normality and homogeneous variance.
- **[Mann-Whitney U Test](https://en.wikipedia.org/wiki/Mann%E2%80%93Whitney_U_test)**: Non-parametric comparison of 2 groups. Used when normality is violated.
- **[Kruskal-Wallis H Test](https://en.wikipedia.org/wiki/Kruskal%E2%80%93Wallis_one-way_analysis_of_variance)**: Non-parametric comparison of 3 or more groups. Used when ANOVA assumptions fail.

#### Clustered / Hierarchical Methods
- **[Linear Mixed Model (LMM)](https://en.wikipedia.org/wiki/Mixed_model)**: Evaluates fixed group effects while modeling random intercepts for clusters to account for intra-cluster correlation.
- **Cluster Mean ANOVA / Kruskal-Wallis**: Aggregates unit observations to cluster-level means before running ANOVA or Kruskal-Wallis, mitigating false significance due to pseudoreplication.
- **Proportion Kruskal-Wallis**: Evaluates binary proportion outcomes aggregated at the cluster level.

#### Discrete Variable Methods
- **[Chi-Square Test of Independence](https://en.wikipedia.org/wiki/Chi-squared_test)**: Evaluates association between categorical variables.

---

### Step 4: Run Evaluation & Review Results
Executes the selected methods and shows an interactive results table containing:
- **Test Statistic**: The calculated value (e.g., $t$, $F$, $H$, $\chi^2$, or $z$).
- **p-value**: Statistical significance. Cells are highlighted green if $p \le 0.01$ (strict significance) or yellow if $p \le 0.05$.
- **Effect Size**: Quantitative measure of the magnitude of the experimental effect.
- **[Intraclass Correlation (ICC)](https://en.wikipedia.org/wiki/Intraclass_correlation)** (Hierarchical only): Indicates the proportion of total variance explained by the clustering level.
- **Statistical Warnings**: Alerts you if assumptions are violated (e.g., severe non-[normality](https://en.wikipedia.org/wiki/Shapiro%E2%80%93Wilk_test), [heteroscedasticity](https://en.wikipedia.org/wiki/Levene%27s_test), or the presence of significant [outliers](https://en.wikipedia.org/wiki/Grubbs%27s_test_for_outliers)).

---

### Step 5: Plot Selection & Preview
Select visualizations to generate for your report. The UI renders live previews using:
- **Box Plot / Violin Plot**: Visualizes group distribution, medians, and quartiles.
- **ECDF (Empirical Cumulative Distribution Function)**: Plots cumulative distributions to compare group spreads.
- **Cluster Mean Bar Plot** (Hierarchical): Displays group means of cluster means with error bars.
- **Cluster Spatial Heatmap** (Spatial): Facilitates spatial pattern analysis by mapping metric values onto X/Y grid coordinates.

---

### Step 6: Export Report
Download your final results and plots in one of these structured formats:
- **PDF Report**: A publication-ready document compiling the test description, evaluation table, decision flags, and embedded high-resolution figures.
- **CSV / JSON Exports**: Standardized raw outputs of the statistical results for downstream pipelines.

---

## Development Workflow & QA

Quality gates are strictly enforced. All tasks can be run via the task runner:

| Command | Description |
|---|---|
| `task install` | Installs dependencies |
| `task lint` | Runs `ruff check` and `ruff format --check` |
| `task format` | Auto-formats code with `ruff` |
| `task typecheck` | Runs `mypy --strict` on code |
| `task test` | Runs the test suite with coverage check (>90% required) |
| `task check` | Runs all quality gates (lint -> typecheck -> test) |
| `task bump -- <patch/minor/major>` | Bumps the application version using `bump-my-version` |

### Project Directory Layout

<details>
<summary>Click to expand directory layout</summary>

```text
├── app/                      # Core FastAPI web application
│   ├── core/                 # Session models, step definitions, and storage interfaces
│   ├── datasets/             # Dataset loading and schema repositories
│   │   ├── models.py         # Dataset Pydantic models
│   │   ├── repository.py     # Dataset loader and repository classes
│   │   └── utils.py          # Column resolution helper functions
│   ├── exporters/            # Extensible export plugins
│   │   ├── base.py           # Exporter base class and registry
│   │   └── builtin/          # Built-in exporters (CSV, JSON, PDF, etc.)
│   ├── filters/              # Extensible preprocessing filters
│   │   ├── base.py           # Filter base class and registry
│   │   └── builtin/          # Built-in filters (numeric range, category filters)
│   ├── main.py               # Application factory and startup orchestrator
│   ├── plots/                # Extensible plot generators
│   │   ├── base.py           # PlotGenerator base class and registry
│   │   └── builtin/          # Built-in plot generators (boxplot, ECDF, violin)
│   ├── static/               # Client-side single-page application
│   │   ├── modules/          # Modular ES6 frontend submodules
│   │   │   ├── api.js        # Backend fetch request wrappers
│   │   │   ├── elements.js   # Cached DOM element references
│   │   │   ├── events.js     # Event listeners registration
│   │   │   ├── helpers.js    # Shared helper utilities and error handlers
│   │   │   ├── navigation.js # Step-by-step panel navigation handlers
│   │   │   ├── state.js      # Global reactive state
│   │   │   └── ui.js         # DOM updates and visual rendering
│   │   ├── app.js            # Main bootstrap entry point
│   │   ├── index.html        # Wizard layout interface
│   │   └── style.css         # Single-green custom-themed Pico CSS overrides
│   ├── stats/                # Extensible statistical plugins
│   │   ├── base.py           # StatMethod ABC, global registry, and re-export facade
│   │   ├── builtin/          # Built-in evaluation methods (t-test, ANOVA, Kruskal-Wallis, etc.)
│   │   ├── models.py         # Schemas and Pydantic models for statistical results
│   │   └── properties.py     # Data properties auto-computation logic
│   └── wizard/               # Router endpoints, request schemas, and transition controls
├── test_data/                # CSV datasets used for verification (e.g., nycflights.csv)
└── tests/                    # QA verification suite (unit, integration, and end-to-end)
```
</details>

---

## Extensibility: Adding Custom Plugins

Adding a new plugin requires **zero changes** to core routing or session orchestration. Simply define a subclass and register it with the appropriate decorator.

### 5-Line Recipe Example

Here is how you can add a custom statistical method in under 10 lines:

```python
from app.stats.base import DataProperties, StatMethod, StatResult, stat_registry

@stat_registry.register("zscore_outliers")
class ZScoreOutliersMethod(StatMethod):
    name = "zscore_outliers"
    description = "Checks for outlier points using Z-score."

    def is_applicable(self, properties: DataProperties) -> bool:
        return properties.n_groups >= 1

    def run(self, groups) -> StatResult:
        # custom calculations...
        return StatResult(
            method_name=self.name,
            test_statistic=1.96,
            p_value=0.05,
            effect_size=None,
            summary="Completed outlier check."
        )
```

The system will automatically:
1. Discover the plugin at startup (under `app/stats/builtin` or when imported).
2. Include it in the `GET /wizard/sessions/{id}/methods` response if `is_applicable` returns `True`.
3. Accept it in `POST /wizard/sessions/{id}/method` and run it during `GET /wizard/sessions/{id}/results`.

The same recipe applies to:
- **Filters**: Inherit `Filter`, register to `filter_registry`.
- **Plots**: Inherit `PlotGenerator`, register to `plot_registry`.
- **Exporters**: Inherit `Exporter`, register to `exporter_registry`.

---

## Statistical Method Selection

In Step 3, the wizard dynamically queries the backend to determine which statistical methods are applicable to your filtered dataset. This process relies on automated data property computation and applicability rules:

1. **Auto-Computation (`compute_data_properties`)**:
   When moving to Step 3, the backend evaluates the dataset properties including:
   - **Normality**: Shapiro-Wilk or D'Agostino-Pearson tests per group.
   - **Variance Homogeneity**: Levene's test to ensure groups have equal variances.
   - **Sphericity**: Mauchly's test for repeated measures (with 3+ conditions).
   - **Expected Cell Counts**: Contingency table evaluation for categorical outcomes.
   - **Missing Data & Outliers**: Automated checks to summarize dataset health.

2. **Applicability Checking (`is_applicable`)**:
   Each registered statistical method implements `is_applicable(properties)` to declare its preconditions:
   - **Independent Two-Sample t-test**: Requires exactly 2 groups of numeric data, with $n \ge 2$ per group, and normality satisfied for all groups.
   - **One-way ANOVA**: Requires $\ge 2$ groups of numeric data, with $n \ge 2$ per group, normality satisfied, and homogeneous variance.
   - **Mann-Whitney U**: Non-parametric; requires exactly 2 groups of numeric data with $n \ge 2$ per group.
   - **Kruskal-Wallis H**: Non-parametric; requires $\ge 2$ groups of numeric data with $n \ge 2$ per group.

If any preconditions are not met, the method is filtered out from the list of selectable options in the GUI.

---

## Hierarchical Data Processing

<details>
<summary>Hierarchical Data Support Logic Details</summary>

### Overview
When "Enable Hierarchical Data Support" is toggled, ExPyRi switches from flat independent evaluation to hierarchical/nested/clustered evaluation. The data levels are defined as:
- **Level 2 (Group)**: Treatment group / experiment arm (discrete)
- **Level 1 (Cluster)**: Intermediate cluster / experimental unit (discrete)
- **Level 0 (Unit)**: Individual observations (lowest level)

### Column Types and Validation
Only continuous and binary proportion dependent columns are supported in hierarchical mode. Multi-class categorical columns (e.g. string columns like `dest` with multiple classes) are not supported.
- **Continuous Columns**: Real-valued numeric measurements.
- **Binary Proportion Columns**: Numeric or boolean columns containing values restricted to `{0, 1, True, False}`.
- **Unsupported Columns**: Non-numeric, non-binary columns. These are classified as `"unsupported"` on the backend and automatically deselected during hierarchical setup, preventing downstream exceptions or crashes.

### Execution Flow
1. **Aggregates Computation**: Cluster-level aggregates (`mean`, `std`, `proportion_corrected`, etc.) are computed.
2. **Properties Auto-Computation**:
   - Normality check (Shapiro-Wilk) is run on the cluster means (not unit observations).
   - Variance homogeneity (Levene's test) is run on the cluster means.
   - Outliers are identified via Grubbs test on cluster means.
   - Intra-class Correlation (ICC) is computed using a Linear Mixed Model (LMM).
3. **Method Selection**: The wizard filters applicable hierarchical methods (e.g., LMM, Cluster Mean ANOVA, Cluster Mean Kruskal-Wallis, or Proportion Kruskal-Wallis).

### Spatial Coordinates (Optional)
If your dataset contains spatial coordinates for each observation (e.g., $X$ and $Y$ coordinates of chips on a wafer in semiconductor manufacturing), you can select the corresponding columns under:
- **X Spatial Coordinate (Optional)**
- **Y Spatial Coordinate (Optional)**

#### What is done with this data?
1. **Exclusion from Metrics**: Like group, cluster, and unit columns, the selected spatial coordinate columns are automatically excluded from the list of analyzed continuous/discrete metrics to avoid redundant evaluation.
2. **Enables Spatial Visualization**: Specifying both $X$ and $Y$ coordinates flags the session as having spatial coordinates (`has_spatial_coords = True`). This enables the **Cluster Spatial Heatmap** (`cluster_spatial_heatmap`) generator in Step 5 (Plot Selection). This plot renders a grid heatmap of unit values plotted against their $X$/$Y$ spatial coordinates, side-by-side (faceted) for each treatment group, letting you easily identify spatial patterns or defects.
</details>
