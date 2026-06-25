"""Shared test fixtures."""

from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Provide an async HTTP test client for the FastAPI app."""
    application = create_app()
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def hierarchical_df() -> Any:
    """Fixture returning a function to generate parameterizable synthetic hierarchical data."""
    import numpy as np
    import pandas as pd

    def _generate(
        n_groups: int = 2,
        n_clusters: int = 4,
        n_units: int = 10,
        is_binary: bool = False,
        imbalanced: bool = False,
        boundary: bool = False,
    ) -> pd.DataFrame:
        np.random.seed(42)  # For deterministic tests
        data = []
        groups = [f"Group_{chr(65 + i)}" for i in range(n_groups)]
        cluster_counter = 0
        unit_counter = 0

        for g_idx, group in enumerate(groups):
            n_c = n_clusters
            if imbalanced:
                n_c = n_clusters + (g_idx * 2 - 1)
                n_c = max(2, n_c)

            for c in range(n_c):
                cluster_id = f"Cluster_{cluster_counter}"
                cluster_counter += 1

                n_u = n_units
                if imbalanced:
                    n_u = n_units + (c % 3 - 1) * 3
                    n_u = max(2, n_u)

                is_boundary_cluster = boundary and (c == 0 and g_idx == 0)

                for u in range(n_u):
                    unit_id = f"Unit_{unit_counter}"
                    unit_counter += 1

                    x = float(c % 4)
                    y = float(u % 4)

                    if is_binary:
                        val = 1.0 if is_boundary_cluster else float(np.random.choice([0.0, 1.0], p=[0.4, 0.6]))
                    else:
                        group_effect = g_idx * 2.0
                        cluster_effect = float(np.random.normal(0, 0.5))
                        unit_noise = float(np.random.normal(0, 1.0))
                        val = 10.0 + group_effect + cluster_effect + unit_noise

                    data.append({"group": group, "cluster": cluster_id, "unit": unit_id, "x": x, "y": y, "metric": val})

        return pd.DataFrame(data)

    return _generate
