"""Wizard dataset configuration service layer.

Handles selecting datasets, configuring group/cluster columns, and resolving dataset schemas.
"""

from __future__ import annotations

import logging
from pathlib import PurePath

from fastapi import HTTPException

from app.core.session import HierarchyConfig, SessionStore, WizardSession
from app.datasets.repository import DatasetRepository
from app.datasets.utils import resolve_selected_discrete_columns, resolve_selected_value_columns
from app.wizard.hierarchy import setup_hierarchy
from app.wizard.steps import WizardStep, reset_to_step, validate_step_transition

logger = logging.getLogger(__name__)


class WizardDatasetService:
    """Handles dataset selection and column configuration for the wizard."""

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

    def _normalize_dataset_id(self, dataset_id: str | None) -> str | None:
        """Map filename-style selections to canonical dataset IDs when possible."""
        if not dataset_id:
            return dataset_id

        available_ids = {dataset.id for dataset in self.repo.list_datasets()}
        if dataset_id in available_ids:
            return dataset_id

        dataset_path = PurePath(dataset_id)
        if dataset_path.suffix and dataset_path.stem in available_ids:
            return dataset_path.stem

        return dataset_id

    def select_dataset_id(self, session_id: str, dataset_id: str | None) -> WizardSession:
        """Select a dataset for the session and reset the workflow to Step 1."""
        session = self.get_session(session_id)
        reset_to_step(session, WizardStep.DATASET_SELECTION)
        session.dataset_id = self._normalize_dataset_id(dataset_id)

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
        """Submit columns configuration and transition to Step 2 (Filters)."""
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

        session.current_step = WizardStep.FILTERS.value
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
