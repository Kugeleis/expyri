"""FastAPI application factory.

Eagerly imports all built-in plugins to ensure registration decorators
fire before the application routes are requested.
"""

from __future__ import annotations

import importlib

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.wizard.router import router
from app.wizard.steps import StepGuardError

# Eagerly import all built-in plugins to trigger decorator registrations
importlib.import_module("app.exporters.builtin")
importlib.import_module("app.filters.builtin")
importlib.import_module("app.plots.builtin")
importlib.import_module("app.stats.builtin")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(
        title="ExpYT — Experiment Evaluation Wizard",
        description="Multi-step wizard for statistical experiment evaluation",
        version="0.1.0",
    )

    # Register router
    application.include_router(router)

    # Register centralized exception handler for step transitions
    @application.exception_handler(StepGuardError)
    def step_guard_error_handler(request: Request, exc: StepGuardError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={
                "detail": str(exc),
                "target": exc.target.value,
                "missing": [s.value for s in exc.missing],
            },
        )

    return application


app: FastAPI = create_app()
