"""Unit tests for main app wiring and dashboard route."""

import pytest
from httpx import ASGITransport, AsyncClient

from soar.db.crud import get_incident
from soar.main import create_app


@pytest.mark.asyncio
async def test_root_endpoint_response_shape():
    """Root endpoint should return basic service metadata."""
    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "SOAR-Lite"
    assert data["docs"] == "/docs"


@pytest.mark.asyncio
async def test_dashboard_route_renders_html(test_client: AsyncClient):
    """Dashboard endpoint should render a basic HTML page."""
    response = await test_client.get("/dashboard")

    assert response.status_code == 200
    assert "SOAR-Lite Operations" in response.text


@pytest.mark.asyncio
async def test_dashboard_incident_detail_renders(test_client: AsyncClient, sample_incident):
    """Incident detail dashboard page should render for existing incidents."""
    response = await test_client.get(f"/dashboard/incidents/{sample_incident.id}")

    assert response.status_code == 200
    assert sample_incident.id in response.text


@pytest.mark.asyncio
async def test_dashboard_verdict_form_updates_incident(
    test_client: AsyncClient,
    sample_incident,
    test_db,
):
    """Verdict form should persist analyst verdict and redirect back to detail page."""
    response = await test_client.post(
        f"/dashboard/incidents/{sample_incident.id}/verdict",
        data={"verdict": "true_positive"},
        follow_redirects=False,
    )

    assert response.status_code == 303

    updated = await get_incident(test_db, sample_incident.id)
    assert updated is not None
    assert updated.analyst_verdict == "true_positive"


def test_dashboard_route_registered():
    """App factory should register /dashboard route."""
    app = create_app()
    paths = {route.path for route in app.routes}
    assert "/dashboard" in paths
    assert "/dashboard/incidents/{incident_id}" in paths
