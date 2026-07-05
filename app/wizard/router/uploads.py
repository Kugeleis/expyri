"""Shared dataset upload helpers for JSON and HTMX routes."""

from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.datasets.models import DatasetInfo
from app.datasets.repository import DatasetRepository


def store_uploaded_dataset(file: UploadFile, repo: DatasetRepository) -> DatasetInfo:
    """Persist an uploaded dataset and return its inferred schema."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename not provided")

    safe_filename = Path(file.filename).name
    if not safe_filename or safe_filename in (".", ".."):
        raise HTTPException(status_code=400, detail="Invalid filename")

    data_dir = getattr(repo, "_data_dir", Path("data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    file_path = data_dir / safe_filename

    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        return repo.get_schema(file_path.stem)
    except KeyError:
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Unsupported file format") from None
