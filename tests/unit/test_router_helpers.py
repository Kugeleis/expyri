"""Tests for shared router helper behavior."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi import UploadFile
from fastapi.responses import JSONResponse
from starlette.requests import Request

from app.core.session import InMemorySessionStore, WizardSession
from app.datasets.repository import MultiFormatDatasetRepository
from app.wizard.router import dependencies
from app.wizard.router.uploads import store_uploaded_dataset


def _request() -> Request:
    return Request({"type": "http", "method": "GET", "path": "/", "headers": []})


def test_store_uploaded_dataset_persists_supported_file(tmp_path: Path) -> None:
    """Uploaded datasets should be stored once and returned with schema metadata."""
    repo = MultiFormatDatasetRepository(tmp_path)
    upload = UploadFile(filename="sample.csv", file=io.BytesIO(b"group,value\nA,1\nB,2\n"))

    dataset = store_uploaded_dataset(upload, repo)

    assert dataset.id == "sample"
    assert (tmp_path / "sample.csv").exists()
    assert [column.name for column in dataset.columns or []] == ["group", "value"]


def test_store_uploaded_dataset_removes_unsupported_file(tmp_path: Path) -> None:
    """Unsupported uploads should not leave unrecognized files in the dataset directory."""
    repo = MultiFormatDatasetRepository(tmp_path)
    upload = UploadFile(filename="sample.txt", file=io.BytesIO(b"not a supported dataset"))

    with pytest.raises(Exception, match="Unsupported file format"):
        store_uploaded_dataset(upload, repo)

    assert not (tmp_path / "sample.txt").exists()


def test_render_step_sorts_copy_without_mutating_session(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Rendering sorted results must not reorder the persisted session state."""
    repo = MultiFormatDatasetRepository(tmp_path)
    store = InMemorySessionStore()
    session = WizardSession(
        current_step="results",
        stat_results=[
            {"column_name": "b", "p_value": 0.2},
            {"column_name": "a", "p_value": 0.1},
        ],
    )

    captured_context: dict[str, object] = {}

    def template_response(*, request: Request, name: str, context: dict[str, object]) -> JSONResponse:
        captured_context.update(context)
        return JSONResponse({"template": name})

    monkeypatch.setattr(dependencies, "get_dataset_repository", lambda: repo)
    monkeypatch.setattr(dependencies.templates, "TemplateResponse", template_response)

    response = dependencies.render_step(_request(), session, store, sort_field="column_name", sort_asc=True)

    assert response.status_code == 200
    rendered_session = captured_context["session"]
    assert isinstance(rendered_session, WizardSession)
    assert [result["column_name"] for result in rendered_session.stat_results] == ["a", "b"]
    assert [result["column_name"] for result in session.stat_results] == ["b", "a"]
