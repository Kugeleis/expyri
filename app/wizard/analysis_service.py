"""Wizard analysis service layer.

Handles execution of statistical tests, visualization generation, and applicability checks.
"""

from __future__ import annotations

import logging

from fastapi import HTTPException

from app.core.session import SessionStore, WizardSession
from app.datasets.repository import DatasetRepository
from app.plots.base import PlotGenerator, plot_registry
from app.stats.base import StatMethod, StatResult, stat_registry
from app.stats.properties import (
    compute_properties,
    compute_properties_for_columns,
)
from app.wizard.filtering import get_filtered_df_with_groups
from app.wizard.plotting import generate_individual_plots, select_top_plot_columns
from app.wizard.statistics import run_stat_for_column
from app.wizard.steps import WizardStep, validate_step_transition

logger = logging.getLogger(__name__)


class WizardAnalysisService:
    """Handles statistical evaluation and plot generation for the wizard."""

    def __init__(self, store: SessionStore, repo: DatasetRepository) -> None:
        """Initialize the service with storage and data repositories."""
        self.store = store
        self.repo = repo

    def get_session(self, session_id: str) -> WizardSession:
        """Retrieve a session by ID or raise 404."""
        session = self.store.get(session_id)
        if session is None:
            raise HTTPException(
                status_code=404,
                detail=f"Wizard session {session_id!r} not found",
            )
        return session

    def _validate_and_save_methods(
        self, session: WizardSession, selected_method: str | None, selected_discrete_method: str | None
    ) -> None:
        """Helper to validate selected methods against registry and save to session."""
        if not selected_method and not selected_discrete_method:
            raise HTTPException(status_code=400, detail="At least one method must be selected")

        if selected_method:
            if selected_method not in stat_registry.list_all():
                raise HTTPException(status_code=400, detail=f"Method {selected_method!r} is not registered")
            session.selected_method = selected_method
        else:
            session.selected_method = None

        if selected_discrete_method:
            if selected_discrete_method not in stat_registry.list_all():
                raise HTTPException(status_code=400, detail=f"Method {selected_discrete_method!r} is not registered")
            session.selected_discrete_method = selected_discrete_method
        else:
            session.selected_discrete_method = None

    def update_method(
        self, session_id: str, selected_method: str | None, selected_discrete_method: str | None
    ) -> WizardSession:
        """Update selected statistical methods in the session."""
        session = self.get_session(session_id)
        session.selected_method = selected_method
        session.selected_discrete_method = selected_discrete_method
        self.store.save(session)
        return session

    def submit_method(
        self, session_id: str, selected_method: str | None, selected_discrete_method: str | None
    ) -> WizardSession:
        """Verify methods, execute evaluations on filtered datasets, and transition to Step 4 (Results)."""
        session = self.get_session(session_id)
        validate_step_transition(session, WizardStep.STAT_METHOD)

        is_incomplete = session.group_column is None or (
            not session.selected_value_columns and not session.selected_discrete_columns
        )
        if is_incomplete:
            raise HTTPException(status_code=400, detail="Incomplete setup")

        filtered_df = get_filtered_df_with_groups(session, self.repo)
        self._validate_and_save_methods(session, selected_method, selected_discrete_method)

        results: list[StatResult] = []
        if session.selected_value_columns and session.selected_method:
            method = stat_registry.get(session.selected_method)
            for val_col in session.selected_value_columns:
                results.append(run_stat_for_column(filtered_df, val_col, method, session))

        if session.selected_discrete_columns and session.selected_discrete_method:
            discrete_method = stat_registry.get(session.selected_discrete_method)
            for disc_col in session.selected_discrete_columns:
                results.append(run_stat_for_column(filtered_df, disc_col, discrete_method, session))

        results.sort(key=lambda r: r.p_value if r.p_value is not None else 1.0)
        session.stat_results = [res.model_dump() for res in results]
        session.current_step = WizardStep.RESULTS.value
        self.store.save(session)
        return session

    def submit_results(self, session_id: str) -> WizardSession:
        """Submit the statistical evaluation and transition to Step 5 (Visualizations)."""
        session = self.get_session(session_id)
        validate_step_transition(session, WizardStep.RESULTS)
        session.current_step = WizardStep.PLOT_SELECTION.value
        self.store.save(session)
        return session

    def generate_plots(
        self,
        session_id: str,
        selected_plots: list[str],
        plots_sig_filter: float,
        top_n_columns: int | None = None,
        theme: str = "dark",
    ) -> WizardSession:
        """Execute plot generation via matplotlib backend and update session state."""
        session = self.get_session(session_id)
        validate_step_transition(session, WizardStep.PLOT_SELECTION)

        is_incomplete = session.group_column is None or (
            not session.selected_value_columns and not session.selected_discrete_columns
        )
        if is_incomplete:
            raise HTTPException(status_code=400, detail="Incomplete setup")

        filtered_df = get_filtered_df_with_groups(session, self.repo)
        top_columns = select_top_plot_columns(session, plots_sig_filter, top_n_columns)
        plot_results = generate_individual_plots(session, filtered_df, top_columns, selected_plots, theme=theme)

        session.selected_plots = selected_plots
        session.top_n_columns = len(top_columns)
        session.plot_results = [p.model_dump() for p in plot_results]
        session.plot_theme = theme
        self.store.save(session)
        return session

    def submit_plots(self, session_id: str) -> WizardSession:
        """Submit visualizations and transition to Step 6 (Export)."""
        session = self.get_session(session_id)
        validate_step_transition(session, WizardStep.PLOT_SELECTION)
        session.current_step = WizardStep.EXPORT.value
        self.store.save(session)
        return session

    def get_applicable_methods(self, session: WizardSession) -> tuple[dict[str, StatMethod], dict[str, StatMethod]]:
        """Compute dataset properties and query registries for applicable statistical methods."""
        applicable_continuous: dict[str, StatMethod] = {}
        applicable_discrete: dict[str, StatMethod] = {}
        if session.current_step != "stat_method":
            return applicable_continuous, applicable_discrete

        try:
            filtered_df = get_filtered_df_with_groups(session, self.repo)
            if session.selected_value_columns:
                props_map = compute_properties_for_columns(session, filtered_df, session.selected_value_columns)
                applicable_continuous = stat_registry.get_applicable_intersect(props_map)
            if session.selected_discrete_columns:
                props_map_discrete = compute_properties_for_columns(
                    session, filtered_df, session.selected_discrete_columns
                )
                applicable_discrete = stat_registry.get_applicable_intersect(props_map_discrete)
        except (AttributeError, KeyError, RuntimeError, TypeError, ValueError):
            logger.exception("Failed to compute applicable methods for session %s", session.session_id)
        return applicable_continuous, applicable_discrete

    def get_applicable_plots(self, session: WizardSession) -> dict[str, PlotGenerator]:
        """Compute dataset properties and query registries for applicable plot generators."""
        applicable_plots: dict[str, PlotGenerator] = {}
        if session.current_step != "plot_selection":
            return applicable_plots

        try:
            filtered_df = get_filtered_df_with_groups(session, self.repo)
            if session.selected_value_columns:
                props = compute_properties(session, filtered_df, session.selected_value_columns[0])
                applicable_plots = plot_registry.get_applicable(props)
        except (AttributeError, KeyError, RuntimeError, TypeError, ValueError):
            logger.exception("Failed to compute applicable plots for session %s", session.session_id)
        return applicable_plots
