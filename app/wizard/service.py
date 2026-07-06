"""Wizard workflow service layer.

Encapsulates all wizard logic, state transitions, validation, and execution
to decouple HTTP endpoints from the core wizard behavior.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from fastapi import HTTPException

from app.core.session import ClusterExclusion, HierarchyConfig, SessionStore, WizardSession
from app.datasets.repository import DatasetRepository
from app.datasets.utils import resolve_selected_discrete_columns, resolve_selected_value_columns
from app.filters.base import apply_filter_pipeline
from app.filters.models import FilterConfigInput, normalize_filter_configs
from app.plots.base import plot_registry
from app.stats.base import StatResult, stat_registry
from app.stats.properties import (
    compute_properties,
    compute_properties_for_columns,
)
from app.wizard.filtering import build_filter_config, extract_cluster_exclusions, get_filtered_df_with_groups
from app.wizard.hierarchy import setup_hierarchy
from app.wizard.plotting import generate_individual_plots, select_top_plot_columns
from app.wizard.statistics import run_stat_for_column
from app.wizard.steps import WizardStep, reset_to_step, validate_step_transition

logger = logging.getLogger(__name__)


class WizardService:
    """Handles business logic, validations, and state changes for the wizard."""

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

    def restart_session(self, session_id: str) -> WizardSession:
        """Create a new session to replace/restart the current one."""
        # Clean up the old session if needed, then create a new one
        return self.store.create()

    def select_dataset_id(self, session_id: str, dataset_id: str | None) -> WizardSession:
        """Select a dataset for the session and reset the workflow to Step 1."""
        session = self.get_session(session_id)
        reset_to_step(session, WizardStep.DATASET_SELECTION)
        session.dataset_id = dataset_id

        if session.dataset_id:
            try:
                df = self.repo.load_dataset(session.dataset_id)
                session.selected_value_columns = resolve_selected_value_columns(df, "", [])
                session.selected_discrete_columns = resolve_selected_discrete_columns(df, "", [])
            except (KeyError, ValueError, TypeError):
                logger.exception("Failed to infer default columns for dataset %s", session.dataset_id)
                session.selected_value_columns = []
                session.selected_discrete_columns = []
        else:
            session.selected_value_columns = []
            session.selected_discrete_columns = []

        self.store.save(session)
        return session

    def toggle_hierarchy(self, session_id: str, enabled: bool) -> WizardSession:
        """Toggle hierarchical support configuration."""
        session = self.get_session(session_id)
        if enabled:
            session.hierarchy = HierarchyConfig(group_col="", cluster_col="")
        else:
            session.hierarchy = None
        self.store.save(session)
        return session

    def update_group_col(self, session_id: str, group_column: str | None) -> WizardSession:
        """Update active group column selection and clear invalid selected value/discrete columns."""
        session = self.get_session(session_id)
        session.group_column = group_column

        if session.group_column:
            if session.group_column in session.selected_value_columns:
                session.selected_value_columns.remove(session.group_column)
            if session.group_column in session.selected_discrete_columns:
                session.selected_discrete_columns.remove(session.group_column)

            if session.hierarchy:
                session.hierarchy.group_col = session.group_column

            if session.dataset_id:
                try:
                    df = self.repo.load_dataset(session.dataset_id)
                    session.selected_groups = sorted(df[session.group_column].dropna().astype(str).unique().tolist())
                except (KeyError, ValueError, TypeError):
                    logger.exception(
                        "Failed to load groups for dataset %s and group column %s",
                        session.dataset_id,
                        session.group_column,
                    )
                    session.selected_groups = []
            else:
                session.selected_groups = []
        else:
            session.selected_groups = []

        self.store.save(session)
        return session

    def update_cluster_col(self, session_id: str, cluster_col: str | None) -> WizardSession:
        """Update hierarchical cluster column selection."""
        session = self.get_session(session_id)
        if not session.hierarchy:
            raise HTTPException(status_code=400, detail="Hierarchical mode is not enabled")

        session.hierarchy.cluster_col = cluster_col or ""
        if cluster_col:
            if cluster_col in session.selected_value_columns:
                session.selected_value_columns.remove(cluster_col)
            if cluster_col in session.selected_discrete_columns:
                session.selected_discrete_columns.remove(cluster_col)

            if session.dataset_id:
                try:
                    df = self.repo.load_dataset(session.dataset_id)
                    session.hierarchy.selected_clusters = sorted(df[cluster_col].dropna().astype(str).unique().tolist())
                except (KeyError, ValueError, TypeError):
                    logger.exception(
                        "Failed to load clusters for dataset %s and cluster column %s",
                        session.dataset_id,
                        cluster_col,
                    )
                    session.hierarchy.selected_clusters = []
            else:
                session.hierarchy.selected_clusters = []
        else:
            session.hierarchy.selected_clusters = []

        self.store.save(session)
        return session

    def submit_dataset_config(
        self,
        session_id: str,
        group_column: str,
        selected_groups: list[str],
        selected_value_columns: list[str],
        selected_discrete_columns: list[str],
        cluster_col: str | None = None,
        selected_clusters: list[str] | None = None,
        unit_col: str | None = None,
        x_col: str | None = None,
        y_col: str | None = None,
    ) -> WizardSession:
        """Submit all Step 1 dataset choices and transition to Step 2 (Filters)."""
        session = self.get_session(session_id)
        validate_step_transition(session, WizardStep.DATASET_SELECTION)

        if not session.dataset_id:
            raise HTTPException(status_code=400, detail="Dataset not selected")

        try:
            schema = self.repo.get_schema(session.dataset_id)
            df = self.repo.load_dataset(session.dataset_id)
        except KeyError:
            raise HTTPException(status_code=400, detail="Dataset not found") from None

        group_col_info = next((col for col in schema.columns or [] if col.name == group_column), None)
        if not group_col_info:
            raise HTTPException(status_code=400, detail=f"Group column {group_column!r} not found")
        if group_col_info.is_numeric:
            raise HTTPException(
                status_code=400,
                detail=f"Group column {group_column!r} must be discrete/categorical, but it is numeric.",
            )

        session.group_column = group_column
        session.selected_groups = selected_groups

        if session.hierarchy:
            if not cluster_col:
                raise HTTPException(status_code=400, detail="Cluster column is required in hierarchical mode")
            setup_hierarchy(
                session,
                schema,
                df,
                group_column,
                cluster_col,
                selected_clusters or [],
                unit_col,
                x_col,
                y_col,
                selected_value_columns,
                selected_discrete_columns,
            )
        else:
            session.selected_value_columns = resolve_selected_value_columns(df, group_column, selected_value_columns)
            session.selected_discrete_columns = resolve_selected_discrete_columns(
                df, group_column, selected_discrete_columns
            )
            session.hierarchy = None
            session.excluded_clusters = []

        if not session.selected_value_columns and not session.selected_discrete_columns:
            raise HTTPException(status_code=400, detail="Select at least one dependent column to analyze.")

        session.current_step = WizardStep.FILTERS.value
        self.store.save(session)
        return session

    def add_filter(
        self,
        session_id: str,
        filter_type: str,
        column: str,
        min_val: str | None = None,
        max_val: str | None = None,
        values: str | None = None,
        exclude: bool = False,
        cluster_id: str | None = None,
        reason: str | None = None,
    ) -> WizardSession:
        """Add a preprocessing filter after dry-running it for validation."""
        session = self.get_session(session_id)
        validate_step_transition(session, WizardStep.FILTERS)

        if session.dataset_id is None:
            raise HTTPException(status_code=400, detail="Dataset not selected")

        try:
            df = self.repo.load_dataset(session.dataset_id)
        except KeyError:
            raise HTTPException(status_code=400, detail="Dataset missing") from None

        new_filter = build_filter_config(filter_type, column, min_val, max_val, values, exclude, cluster_id, reason)

        test_configs = session.filters_config + [new_filter]
        try:
            apply_filter_pipeline(df, test_configs)
        except (KeyError, ValueError, TypeError) as e:
            raise HTTPException(status_code=400, detail=f"Invalid filter parameters: {e}") from None

        session.filters_config = test_configs

        if filter_type == "cluster_exclusion" and cluster_id and reason:
            session.excluded_clusters.append(ClusterExclusion(cluster_id=cluster_id, reason=reason))

        self.store.save(session)
        return session

    def delete_filter(self, session_id: str, index: int) -> WizardSession:
        """Remove a preprocessing filter by its index position."""
        session = self.get_session(session_id)
        validate_step_transition(session, WizardStep.FILTERS)

        if index < 0 or index >= len(session.filters_config):
            raise HTTPException(status_code=400, detail="Filter index out of range")

        removed = session.filters_config.pop(index)

        if removed.name == "cluster_exclusion":
            exclusions_list = removed.params.get("exclusions", [])
            for item in exclusions_list:
                session.excluded_clusters = [
                    ex for ex in session.excluded_clusters if ex.cluster_id != str(item["cluster_id"])
                ]

        self.store.save(session)
        return session

    def configure_filters(self, session_id: str, filters_config: Sequence[FilterConfigInput]) -> WizardSession:
        """JSON compatibility: configure and apply a batch of preprocessing filters."""
        session = self.get_session(session_id)
        validate_step_transition(session, WizardStep.FILTERS)

        if session.dataset_id is None:
            raise HTTPException(status_code=400, detail="Dataset not selected")

        try:
            df = self.repo.load_dataset(session.dataset_id)
        except KeyError:
            raise HTTPException(status_code=400, detail="Dataset missing") from None

        try:
            normalized_filters = normalize_filter_configs(filters_config)
            apply_filter_pipeline(df, normalized_filters)
        except (KeyError, ValueError, TypeError) as e:
            raise HTTPException(status_code=400, detail=str(e)) from None

        session.filters_config = normalized_filters

        session.excluded_clusters = extract_cluster_exclusions(normalized_filters)

        session.current_step = WizardStep.STAT_METHOD.value
        self.store.save(session)
        return session

    def submit_filters(self, session_id: str) -> WizardSession:
        """Confirm the configured filters and move to Step 3 (Choose Method)."""
        session = self.get_session(session_id)
        validate_step_transition(session, WizardStep.FILTERS)
        session.current_step = WizardStep.STAT_METHOD.value
        self.store.save(session)
        return session

    def update_method(
        self, session_id: str, selected_method: str | None, selected_discrete_method: str | None
    ) -> WizardSession:
        """Update selected statistical methods in the session."""
        session = self.get_session(session_id)
        session.selected_method = selected_method
        session.selected_discrete_method = selected_discrete_method
        self.store.save(session)
        return session

    def _validate_and_save_methods(
        self, session: WizardSession, selected_method: str | None, selected_discrete_method: str | None
    ) -> None:
        """Helper to validate and assign method options in the session."""
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

    def navigate(self, session_id: str, direction: str) -> WizardSession:
        """Navigate backward or forward through steps."""
        session = self.get_session(session_id)
        steps_list = list(WizardStep)
        current_idx = steps_list.index(WizardStep(session.current_step))

        if direction == "back":
            if current_idx == 0:
                raise HTTPException(status_code=400, detail="Cannot navigate back from first step")
            target = steps_list[current_idx - 1]
            reset_to_step(session, target)
        else:
            if current_idx == len(steps_list) - 1:
                raise HTTPException(status_code=400, detail="Cannot navigate forward from last step")
            target = steps_list[current_idx + 1]
            validate_step_transition(session, target)
            session.current_step = target.value

        self.store.save(session)
        return session

    def go_to_step(self, session_id: str, target_step: str) -> WizardSession:
        """Direct navigation to a step with transition validations."""
        session = self.get_session(session_id)
        try:
            target = WizardStep(target_step)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unknown wizard step {target_step!r}") from None

        current = WizardStep(session.current_step)
        steps_list = list(WizardStep)
        current_idx = steps_list.index(current)
        target_idx = steps_list.index(target)
        is_forward = target_idx > current_idx

        if is_forward:
            validate_step_transition(session, target)
            session.current_step = target.value
        else:
            reset_to_step(session, target)

        self.store.save(session)
        return session

    def get_available_groups_and_clusters(self, session: WizardSession) -> tuple[list[str], list[str]]:
        """Retrieve sorted unique group values and cluster values for the active dataset."""
        groups: list[str] = []
        clusters: list[str] = []
        if not session.dataset_id:
            return groups, clusters

        try:
            df = self.repo.load_dataset(session.dataset_id)
            if session.group_column:
                groups = sorted(df[session.group_column].dropna().astype(str).unique().tolist())
            if session.hierarchy and session.hierarchy.cluster_col:
                clusters = sorted(df[session.hierarchy.cluster_col].dropna().astype(str).unique().tolist())
        except (KeyError, ValueError, TypeError):
            logger.exception("Failed to load available groups or clusters for session %s", session.session_id)
        return groups, clusters

    def get_applicable_methods(self, session: WizardSession) -> tuple[dict[str, Any], dict[str, Any]]:
        """Compute dataset properties and query registries for applicable statistical methods."""
        applicable_continuous: dict[str, Any] = {}
        applicable_discrete: dict[str, Any] = {}
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

    def get_applicable_plots(self, session: WizardSession) -> dict[str, Any]:
        """Compute dataset properties and query registries for applicable plot generators."""
        applicable_plots: dict[str, Any] = {}
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
