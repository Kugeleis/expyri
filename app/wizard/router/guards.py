"""Wizard route guards.

Provides dependency factories to validate step transitions before endpoints run.
"""

from __future__ import annotations

from typing import Callable

from fastapi import Depends

from app.core.session import WizardSession
from app.wizard.router.dependencies import get_session
from app.wizard.steps import WizardStep, validate_step_transition


def require_step(step: WizardStep) -> Callable[[WizardSession], WizardSession]:
    """Return a dependency that validates transition to a specific step."""

    def dependency(session: WizardSession = Depends(get_session)) -> WizardSession:
        validate_step_transition(session, step)
        return session

    return dependency
