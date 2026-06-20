"""Dataset Pydantic models."""

from __future__ import annotations

from pydantic import BaseModel


class ColumnInfo(BaseModel):
    """Schema information for a single dataset column."""

    name: str
    dtype: str
    nullable: bool = True


class DatasetInfo(BaseModel):
    """Metadata describing a dataset."""

    id: str
    name: str
    description: str = ""
    columns: list[ColumnInfo] = []
