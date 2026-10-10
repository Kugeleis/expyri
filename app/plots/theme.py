"""Shared Matplotlib styling for generated plot images."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any, BinaryIO, Literal

import matplotlib.pyplot as plt
from matplotlib.figure import Figure

PlotTheme = Literal["light", "dark"]

PLOT_BACKGROUNDS: dict[PlotTheme, str] = {
    "light": "#f5f6f8",
    "dark": "#11141c",
}

PLOT_RC: dict[PlotTheme, dict[Any, Any]] = {
    "light": {
        "figure.facecolor": PLOT_BACKGROUNDS["light"],
        "axes.facecolor": PLOT_BACKGROUNDS["light"],
        "savefig.facecolor": PLOT_BACKGROUNDS["light"],
        "savefig.edgecolor": PLOT_BACKGROUNDS["light"],
        "text.color": "#17212f",
        "axes.labelcolor": "#17212f",
        "axes.titlecolor": "#17212f",
        "axes.edgecolor": "#9aa7b5",
        "xtick.color": "#17212f",
        "ytick.color": "#17212f",
        "grid.color": "#d7dde5",
        "legend.facecolor": PLOT_BACKGROUNDS["light"],
        "legend.edgecolor": "#cbd5e1",
    },
    "dark": {
        "figure.facecolor": PLOT_BACKGROUNDS["dark"],
        "axes.facecolor": PLOT_BACKGROUNDS["dark"],
        "savefig.facecolor": PLOT_BACKGROUNDS["dark"],
        "savefig.edgecolor": PLOT_BACKGROUNDS["dark"],
        "text.color": "#f1f3f9",
        "axes.labelcolor": "#f1f3f9",
        "axes.titlecolor": "#f1f3f9",
        "axes.edgecolor": "#7b8493",
        "xtick.color": "#f1f3f9",
        "ytick.color": "#f1f3f9",
        "grid.color": "#3b4250",
        "legend.facecolor": PLOT_BACKGROUNDS["dark"],
        "legend.edgecolor": "#3b4250",
    },
}


def normalize_plot_theme(theme: str | None) -> PlotTheme:
    """Return a supported plot theme name."""
    return "light" if theme == "light" else "dark"


@contextmanager
def plot_context(theme: str | None = "dark") -> Generator[None]:
    """Render plots with a theme isolated from global Matplotlib styles."""
    normalized_theme = normalize_plot_theme(theme)
    with plt.style.context("default"), plt.rc_context(PLOT_RC[normalized_theme]):
        yield


@contextmanager
def light_plot_context() -> Generator[None]:
    """Render plots with a very light grey background, isolated from global styles."""
    with plot_context("light"):
        yield


def save_plot(fig: Figure, buf: BinaryIO, theme: str | None = "dark", **kwargs: Any) -> None:
    """Save a figure while preserving the selected plot background."""
    background = PLOT_BACKGROUNDS[normalize_plot_theme(theme)]
    fig.savefig(buf, facecolor=background, edgecolor=background, **kwargs)


def save_light_plot(fig: Figure, buf: BinaryIO, **kwargs: Any) -> None:
    """Save a figure while preserving the shared light-grey plot background."""
    save_plot(fig, buf, theme="light", **kwargs)
