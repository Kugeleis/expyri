"""Typed filter configuration models."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FilterConfig(BaseModel):
    """Configuration for one preprocessing filter in a wizard session."""

    model_config = ConfigDict(extra="allow")

    name: str | None = Field(None, description="Name of the filter plugin.")
    params: Any = Field(default_factory=dict, description="Configuration parameters.")
    column: str | None = Field(None, description="Display column used by form-based filters.")


FilterConfigInput = FilterConfig | Mapping[str, Any]


def normalize_filter_config(config: FilterConfigInput) -> FilterConfig:
    """Return a FilterConfig instance from a model or mapping."""
    if isinstance(config, FilterConfig):
        return config
    return FilterConfig.model_validate(config)


def normalize_filter_configs(configs: Sequence[FilterConfigInput]) -> list[FilterConfig]:
    """Normalize a sequence of filter config inputs."""
    return [normalize_filter_config(config) for config in configs]


def dump_filter_configs(configs: Sequence[FilterConfigInput]) -> list[dict[str, Any]]:
    """Serialize filter configs for JSON metadata while omitting empty defaults."""
    return [normalize_filter_config(config).model_dump(exclude_none=True, exclude_defaults=True) for config in configs]
