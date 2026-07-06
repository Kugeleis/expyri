from __future__ import annotations

import base64
import io
import logging
import os
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
from typing import cast

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from fastapi import Depends, HTTPException, Request, Response
from fastapi.templating import Jinja2Templates

from app.core.session import InMemorySessionStore, SessionStore, WizardSession
from app.datasets.repository import DatasetRepository, MultiFormatDatasetRepository
from app.filters.base import apply_filter_pipeline
from app.plots.theme import normalize_plot_theme, plot_context, save_plot
from app.stats.base import stat_registry
from app.wizard.plotting import generate_individual_plots, select_top_plot_columns
from app.wizard.service import WizardService
from app.wizard.steps import _completed_steps

templates = Jinja2Templates(directory="app/templates")


_fallback_store: SessionStore = InMemorySessionStore()
logger = logging.getLogger(__name__)


def _applicable_first(methods: list[tuple[str, Any]], applicable: dict[str, Any]) -> list[tuple[str, Any]]:
    """Keep registry order while showing currently applicable methods first."""
    if not applicable:
        return methods
    return [item for item in methods if item[0] in applicable] + [item for item in methods if item[0] not in applicable]


def get_session_store(request: Request = None) -> SessionStore:  # type: ignore[assignment]
    """Dependency provider for the SessionStore."""
    if request is None:
        return _fallback_store
    if not hasattr(request.app.state, "session_store"):
        request.app.state.session_store = InMemorySessionStore()
    return cast(SessionStore, request.app.state.session_store)


def get_dataset_repository() -> DatasetRepository:
    """Dependency provider for the DatasetRepository."""
    data_dir = Path(os.getenv("EXPYRI_DATA_DIR", "data"))
    return MultiFormatDatasetRepository(data_dir)


def get_wizard_service(
    store: SessionStore = Depends(get_session_store),
    repo: DatasetRepository = Depends(get_dataset_repository),
) -> WizardService:
    """Dependency provider for the WizardService."""
    return WizardService(store, repo)


def get_session(
    session_id: str,
    store: SessionStore = Depends(get_session_store),
) -> WizardSession:
    """Fetch the wizard session by ID or raise 404."""
    session = store.get(session_id)
    if session is None:
        raise HTTPException(
            status_code=404,
            detail=f"Wizard session {session_id!r} not found",
        )
    return session


def get_filtered_dataset(
    session: WizardSession,
    repo: DatasetRepository,
) -> pd.DataFrame:
    """Load the dataset and apply the session's filter pipeline."""
    if session.dataset_id is None:
        raise HTTPException(status_code=400, detail="Dataset not selected")

    try:
        df = repo.load_dataset(session.dataset_id)
    except KeyError:
        raise HTTPException(status_code=400, detail="Dataset missing") from None

    try:
        df = apply_filter_pipeline(df, session.filters_config)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Filter registration missing: {e}") from None

    if session.group_column and session.selected_groups:
        df = df[df[session.group_column].astype(str).isin(session.selected_groups)]
    if session.hierarchy and session.hierarchy.selected_clusters:
        df = df[df[session.hierarchy.cluster_col].astype(str).isin(session.hierarchy.selected_clusters)]
    return df


def generate_significance_chart_base64(
    stat_results: list[dict[str, Any]],
    limit: float,
    theme: str = "dark",
) -> str | None:
    """Generate a significance scatter plot of p-values using matplotlib and encode it to base64."""
    valid_results = [res for res in stat_results if res.get("p_value") is not None]
    if not valid_results:
        return None

    valid_results.sort(key=lambda x: x["p_value"])
    labels = [res.get("column_name") or "Unknown" for res in valid_results]
    p_values = [res["p_value"] for res in valid_results]
    strict_limit = limit * 0.2

    plot_theme = normalize_plot_theme(theme)

    with plot_context(plot_theme):
        fig, ax = plt.subplots(figsize=(8, 3.5))

        ax.axhline(
            y=limit,
            color=(250 / 255, 204 / 255, 21 / 255, 0.65),
            linestyle="--",
            label=f"p-value Limit ({limit})",
        )
        ax.axhline(
            y=strict_limit,
            color=(16 / 255, 185 / 255, 129 / 255, 0.65),
            linestyle="--",
            label=f"Strict Limit ({strict_limit:.3f})",
        )

        ax.axhspan(0, strict_limit, color="#10b981", alpha=0.1)
        ax.axhspan(strict_limit, limit, color="#facc15", alpha=0.12)

        colors = []
        for p in p_values:
            if p <= strict_limit:
                colors.append("#10b981")
            elif p <= limit:
                colors.append("#facc15")
            else:
                colors.append("#475569" if plot_theme == "light" else "#d1d5db")

        x_indices = np.arange(len(labels))
        point_edge = (15 / 255, 23 / 255, 42 / 255, 0.25) if plot_theme == "light" else (1, 1, 1, 0.25)
        ax.scatter(x_indices, p_values, color=colors, edgecolor=point_edge, s=60, zorder=5)

        ax.set_xticks(x_indices)
        ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=9)
        ax.set_ylabel("p-value", fontsize=10)
        ax.set_title("Statistical Significance by Column", fontsize=11)
        ax.set_ylim(-0.02, 1.02)

        ax.grid(True, linestyle=":", alpha=0.45)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        plt.tight_layout()

        buf = io.BytesIO()
        try:
            save_plot(fig, buf, theme=plot_theme, format="png", bbox_inches="tight", dpi=100)
            buf.seek(0)
            img_str = base64.b64encode(buf.read()).decode("utf-8")
        finally:
            plt.close(fig)

    return img_str


def _refresh_plot_theme_if_needed(
    session: WizardSession,
    store: SessionStore,
    repo: DatasetRepository,
    plots_sig_filter: float,
    plot_theme: str,
) -> None:
    """Regenerate stored plot PNGs when the app theme changes."""
    if not (
        session.current_step in ("plot_selection", "export")
        and session.plot_results
        and session.selected_plots
        and session.plot_theme != plot_theme
    ):
        return

    try:
        filtered_df = get_filtered_dataset(session, repo)
        top_columns = select_top_plot_columns(session, plots_sig_filter)
        plot_results = generate_individual_plots(
            session,
            filtered_df,
            top_columns,
            session.selected_plots,
            theme=plot_theme,
        )
        session.top_n_columns = len(top_columns)
        session.plot_results = [plot.model_dump() for plot in plot_results]
        session.plot_theme = plot_theme
        store.save(session)
    except (KeyError, TypeError, ValueError):
        logger.exception("Failed to refresh plot theme for session %s", session.session_id)


def render_step(
    request: Request,
    session: WizardSession,
    store: SessionStore,
    plots_sig_filter: float = 0.05,
    sort_field: str = "column_name",
    sort_asc: bool = True,
    repo: DatasetRepository | None = None,
) -> Response:
    """Helper to render either the full workspace or HTMX out-of-band updates."""
    completed = _completed_steps(session)
    completed_names = {s.value for s in completed}

    columns: list[Any] = []
    applicable_continuous: dict[str, Any] = {}
    applicable_discrete: dict[str, Any] = {}
    applicable_plots: dict[str, Any] = {}
    sig_chart_base64: str | None = None
    matched_count = 0
    plot_theme = normalize_plot_theme(request.cookies.get("expyri_theme"))

    active_repo = repo or get_dataset_repository()
    service = WizardService(store, active_repo)

    if session.dataset_id:
        try:
            columns = active_repo.get_schema(session.dataset_id).columns or []
        except (AttributeError, KeyError, TypeError, ValueError):
            logger.exception("Failed to load schema for dataset %s while rendering wizard", session.dataset_id)

    available_groups, available_clusters = service.get_available_groups_and_clusters(session)

    if session.current_step == "stat_method":
        applicable_continuous, applicable_discrete = service.get_applicable_methods(session)

    elif session.current_step in ("results", "plot_selection", "export"):
        if session.stat_results:
            matched_count = sum(
                1
                for res in session.stat_results
                if res.get("p_value") is not None and res["p_value"] <= plots_sig_filter
            )
            sig_chart_base64 = generate_significance_chart_base64(
                session.stat_results,
                plots_sig_filter,
                theme=plot_theme,
            )

        _refresh_plot_theme_if_needed(session, store, active_repo, plots_sig_filter, plot_theme)

        if session.current_step == "plot_selection":
            applicable_plots = service.get_applicable_plots(session)

    render_session = session.model_copy(deep=True)

    if render_session.stat_results:

        def sort_key(x: dict[str, Any]) -> tuple[bool, Any]:
            val = x.get(sort_field)
            return (val is None, val)

        render_session.stat_results = sorted(render_session.stat_results, key=sort_key, reverse=not sort_asc)

    continuous_methods = [(name, method) for name, method in stat_registry.list_all().items() if name != "chi_square"]
    discrete_methods = [(name, method) for name, method in stat_registry.list_all().items() if name == "chi_square"]

    context = {
        "request": request,
        "app_version": getattr(request.scope.get("app"), "version", "0.1.0"),
        "session": render_session,
        "completed_steps": completed_names,
        "is_step_completed": session.current_step in completed_names,
        "columns": columns,
        "available_groups": available_groups,
        "available_clusters": available_clusters,
        "continuous_methods": _applicable_first(continuous_methods, applicable_continuous),
        "discrete_methods": _applicable_first(discrete_methods, applicable_discrete),
        "applicable_continuous": applicable_continuous,
        "applicable_discrete": applicable_discrete,
        "applicable_plots": applicable_plots,
        "sig_chart_base64": sig_chart_base64,
        "plots_sig_filter": plots_sig_filter,
        "matched_count": matched_count,
        "sort_field": sort_field,
        "sort_asc": sort_asc,
        "datasets": active_repo.list_datasets(),
    }

    if "hx-request" in request.headers:
        return templates.TemplateResponse(request=request, name="layouts/oob_update.html", context=context)
    else:
        return templates.TemplateResponse(request=request, name="base.html", context=context)
