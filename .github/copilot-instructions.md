# ExPyRi Repository Instructions

## Build, test, and lint

- Install/synchronize dependencies: `uv sync`
- Run the development server: `task dev` (Uvicorn on `127.0.0.1:8765`)
- Run one test: `uv run pytest tests/unit/test_registry.py::test_register_and_get`
  - Substitute a test file, class, or test function to focus on other tests; run a file with `uv run pytest tests/unit/test_registry.py`.
- Run the full local test suite with coverage: `task test` (runs prek checks and pytest; coverage must be at least 90%).
- Run Python lint and formatting checks: `uv run ruff check .` and `uv run ruff format --check .`; run JS/CSS/HTML checks with `task lint:js`.
- Run type checking: `uv run ty check app` or `task typecheck`.
- Run all quality gates: `task check`.
- Build the container: `task docker:build`. Build documentation with `task docs:build`.

CI runs Ruff, JS checks, `ty`, and pytest; its pytest command excludes `tests/e2e/test_playwright_e2e.py` and uses an 80% coverage threshold.

## Architecture

ExPyRi is a FastAPI application that serves both an HTMX-driven wizard and JSON API routes. `app/main.py` creates the application, initializes the session store, mounts static assets, and eagerly imports built-in plugin packages so their registration decorators run at startup.

Wizard HTTP endpoints are grouped under `app/wizard/router/` by UI/API flow. Keep request/response handling in routers and put workflow behavior in the wizard services: `WizardService` handles session and step transitions, while dataset and analysis services coordinate dataset setup, filtering, statistical evaluation, and plotting. Step prerequisites and backward-navigation resets are centralized in `app/wizard/steps.py`.

The services depend on the `SessionStore` and `DatasetRepository` interfaces rather than storage implementations. Sessions hold the state of the multi-step workflow; repositories and file loaders isolate dataset discovery, schema inspection, and loading. Filters, statistical methods, plots, and exporters are separate extension points backed by registries in `app/core/registry.py`.

Templates and static assets implement the HTMX UI; JavaScript enhances targeted interactions rather than owning the wizard workflow. Tests are organized as unit, integration, and end-to-end coverage; browser flows use Playwright.

## Key conventions

- Add built-in plugins in the relevant `app/{filters,stats,plots,exporters}/builtin/` package. Inherit the matching base class, register with that subsystem's registry decorator, and make the package import the plugin module so `app.main`'s eager built-in import registers it. Registry decorators instantiate plugin classes without arguments.
- Statistical methods and plots declare data-dependent eligibility through `is_applicable(properties)`. Methods receive grouped flat or hierarchical data through the shared analysis flow; account for both supported modes where the method is intended to support them. For multi-column selection, applicable methods are intersected across selected columns.
- Filters validate their configuration in `validate_params` and transform the DataFrame in `apply`; the shared pipeline applies configured filters in order to a copy of the source DataFrame.
- Use FastAPI dependency injection and the `SessionStore`/`DatasetRepository` protocols at route and service boundaries. Keep routers thin and centralize wizard state transitions and prerequisite checks rather than reimplementing them in endpoints.
- Preserve the HTMX/template flow for interactive UI updates and keep client-side behavior in the existing static assets; use the JSON routes for API clients.
- Follow the existing Ruff configuration (Python 3.12 target, 120-character line length). Keep source files focused and generally under 300 lines, and maintain at least 90% local test coverage. `tests/conftest.py` provides a deterministic `hierarchical_df` fixture for hierarchical-data tests.

See [README.md](../README.md) for the user workflow, detailed plugin recipe, and statistical/hierarchical behavior. Shared project design and quality rules are also in [.agents/AGENTS.md](../.agents/AGENTS.md).
