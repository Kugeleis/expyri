"""Wizard workflow service layer.

Encapsulates all wizard logic, state transitions, validation, and execution
to decouple HTTP endpoints from the core wizard behavior.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from fastapi import HTTPException

from app.core.session import ClusterExclusion, SessionStore, WizardSession
from app.datasets.repository import DatasetRepository
from app.filters.base import apply_filter_pipeline
from app.filters.models import FilterConfigInput, normalize_filter_configs
from app.wizard.filtering import build_filter_config, extract_cluster_exclusions
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
        return self.store.create()

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
