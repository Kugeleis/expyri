# ExpYT — Experiment Evaluation Wizard

ExpYT is a modular, extensible FastAPI backend that guides users through a multi-step statistical evaluation wizard: **Dataset Selection → Preprocessing Filters → Statistical Method → Run Evaluation → Plot Selection → Report Export**.

The project is built on SOLID open/closed principles, allowing developers to add new filters, statistical methods, plots, and exporters as plugins without modifying the core API router or orchestration logic.

---

## Architecture Diagram

The wizard maintains state using an in-memory session store (interfaced via a protocol dependency, allowing easy swap to Redis/DB). Each stage is guarded by step prerequisites. Applicability guards query registries to list options suited to the dataset's current characteristics (e.g., number of groups, normality, homogeneity of variance).

```mermaid
graph TD
    subgraph Registries [Plugin Registries]
        FR[filter_registry: Registry[Filter]]
        SR[stat_registry: Registry[StatMethod]]
        PR[plot_registry: Registry[PlotGenerator]]
        ER[exporter_registry: Registry[Exporter]]
    end

    subgraph Flow [Wizard Steps]
        S1[1. Dataset Selection] --> S2[2. Preprocessing Filters]
        S2 --> S3[3. Statistical Method Selection]
        S3 --> S4[4. Run Evaluation]
        S4 --> S5[5. Plot Selection]
        S5 --> S6[6. Report Export]
    end

    S2 -.->|Queries & Executes| FR
    S3 -.->|Filters Applicable| SR
    S5 -.->|Filters Applicable| PR
    S6 -.->|Generates Format| ER
```

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

---

## Extensibility: Adding Custom Plugins

Adding a new plugin requires **zero changes** to core routing or session orchestration. Simply define a subclass and register it with the appropriate decorator.

### 5-Line Recipe Example

Here is how you can add a custom statistical method in under 10 lines:

```python
from app.stats.base import StatMethod, StatResult, stat_registry

@stat_registry.register("zscore_outliers")
class ZScoreOutliersMethod(StatMethod):
    name = "zscore_outliers"
    description = "Checks for outlier points using Z-score."

    def is_applicable(self, **properties) -> bool:
        return properties.get("n_groups", 0) >= 1

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
