"""Smoke test for the FastAPI application."""

from httpx import AsyncClient


async def test_app_starts(client: AsyncClient) -> None:
    """The application should respond to OpenAPI docs endpoint."""
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert data["info"]["title"] == "ExpYT — Experiment Evaluation Wizard"


async def test_root_serves_homepage(client: AsyncClient) -> None:
    """The root URL should serve the wizard homepage HTML."""
    response = await client.get("/")
    assert response.status_code == 200
    assert "ExpYT" in response.text
    assert "Experiment Evaluation Wizard" in response.text
