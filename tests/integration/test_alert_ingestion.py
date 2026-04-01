"""Integration tests for alert ingestion and playbook execution."""


import pytest
from httpx import AsyncClient

from soar.db.crud import get_incident


@pytest.mark.asyncio
async def test_alert_ingestion_and_matching(test_client: AsyncClient):
    """Test: POST alert → playbook matches → incident created."""
    alert_data = {
        "alert_type": "phishing",
        "severity": "high",
        "source_ip": "192.168.1.100",
        "source_system": "mock",
    }

    response = await test_client.post("/alerts/", json=alert_data)

    assert response.status_code == 202
    data = response.json()
    assert "incident_id" in data
    assert data["playbook_matched"] == "phishing_triage"
    assert data["status"] == "accepted"


@pytest.mark.asyncio
async def test_no_playbook_match(test_client: AsyncClient):
    """Test: Alert with no matching playbook returns 400."""
    alert_data = {
        "alert_type": "unknown_alert_type",
        "severity": "low",
        "source_ip": "192.168.1.100",
        "source_system": "mock",
    }

    response = await test_client.post("/alerts/", json=alert_data)

    assert response.status_code == 400
    data = response.json()
    assert "No playbook matched" in data.get("detail", "")


@pytest.mark.asyncio
async def test_missing_source_system(test_client: AsyncClient):
    """Test: Alert missing source_system returns 400."""
    alert_data = {
        "alert_type": "phishing",
        "severity": "high",
        "source_ip": "192.168.1.100",
    }

    response = await test_client.post("/alerts/", json=alert_data)

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_list_incidents(test_client: AsyncClient, sample_incident):
    """Test: GET /incidents returns paginated list."""
    response = await test_client.get("/incidents/")

    assert response.status_code == 200
    data = response.json()
    assert "incidents" in data
    assert "total" in data
    assert "page" in data
    assert isinstance(data["incidents"], list)


@pytest.mark.asyncio
async def test_get_incident_detail(test_client: AsyncClient, sample_incident):
    """Test: GET /incidents/{id} returns full incident detail."""
    response = await test_client.get(f"/incidents/{sample_incident.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == sample_incident.id
    assert "alert" in data
    assert "steps" in data


@pytest.mark.asyncio
async def test_incident_not_found(test_client: AsyncClient):
    """Test: GET /incidents/{id} with invalid ID returns 404."""
    response = await test_client.get("/incidents/invalid-id-12345")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_verdict(test_client: AsyncClient, sample_incident, test_db):
    """Test: PATCH /incidents/{id}/verdict updates analyst verdict."""
    response = await test_client.patch(
        f"/incidents/{sample_incident.id}/verdict",
        json={"verdict": "true_positive"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["analyst_verdict"] == "true_positive"

    # Verify in database
    updated_incident = await get_incident(test_db, sample_incident.id)
    assert updated_incident.analyst_verdict == "true_positive"


@pytest.mark.asyncio
async def test_invalid_verdict(test_client: AsyncClient, sample_incident):
    """Test: PATCH with invalid verdict returns 400."""
    response = await test_client.patch(
        f"/incidents/{sample_incident.id}/verdict",
        json={"verdict": "invalid"},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_health_check(test_client: AsyncClient):
    """Test: GET /health returns connector status."""
    response = await test_client.get("/health/")

    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "connectors" in data


@pytest.mark.asyncio
async def test_list_playbooks(test_client: AsyncClient):
    """Test: GET /playbooks returns loaded playbooks."""
    response = await test_client.get("/playbooks/")

    assert response.status_code == 200
    data = response.json()
    assert "playbooks" in data
    assert len(data["playbooks"]) > 0


@pytest.mark.asyncio
async def test_get_analytics_summary(test_client: AsyncClient):
    """Test: GET /analytics/summary returns statistics."""
    response = await test_client.get("/analytics/summary")

    assert response.status_code == 200
    data = response.json()
    assert "total_incidents" in data
    assert "by_status" in data
    assert "connector_error_rates" in data
