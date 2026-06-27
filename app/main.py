"""FastAPI application factory.

Eagerly imports all built-in plugins to ensure registration decorators
fire before the application routes are requested.
"""

from __future__ import annotations

import importlib
import importlib.metadata
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.wizard.router import router
from app.wizard.steps import StepGuardError

# Eagerly import all built-in plugins to trigger decorator registrations
importlib.import_module("app.exporters.builtin")
importlib.import_module("app.filters.builtin")
importlib.import_module("app.plots.builtin")
importlib.import_module("app.stats.builtin")

try:
    __version__ = importlib.metadata.version("expyri")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.1.0"


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(
        title="ExPyRi — Experiment Evaluation Wizard",
        description="Multi-step wizard for statistical experiment evaluation",
        version=__version__,
    )

    # Register router
    application.include_router(router)

    # Mount static files at root
    application.mount("/", StaticFiles(directory="app/static", html=True), name="static")

    # Add middleware to disable caching for static assets during development
    @application.middleware("http")
    async def add_no_cache_headers(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        path = request.url.path
        if path.endswith((".css", ".js", ".html")) or path == "/":
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

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
