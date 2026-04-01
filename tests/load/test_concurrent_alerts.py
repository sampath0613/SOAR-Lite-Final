"""Load tests for concurrent alert processing."""

import asyncio

import pytest
from httpx import AsyncClient



@pytest.mark.asyncio
async def test_concurrent_alert_ingestion(test_client: AsyncClient):
    """Test: System handles 50 concurrent alerts without issues."""
    alerts = [
        {
            "alert_type": "phishing",
            "severity": "high",
            "source_ip": f"192.168.1.{i}",
            "source_system": "mock",
        }
        for i in range(50)
    ]

    # Fire all alerts concurrently
    tasks = [test_client.post("/alerts/", json=alert) for alert in alerts]
    responses = await asyncio.gather(*tasks)

    # All should return 202 Accepted
    assert all(r.status_code == 202 for r in responses)

    # All should have unique incident IDs
    incident_ids = [r.json()["incident_id"] for r in responses]
    assert len(set(incident_ids)) == 50  # All unique
    assert all("incident_id" in r.json() for r in responses)


@pytest.mark.asyncio
async def test_concurrent_alert_various_types(test_client: AsyncClient):
    """Test: System handles concurrent alerts of different types."""
    alert_types = ["phishing", "malware", "bruteforce", "suspicious_domain", "c2_communication"]
    severities = ["low", "medium", "high", "critical"]

    alerts = [
        {
            "alert_type": alert_types[i % len(alert_types)],
            "severity": severities[i % len(severities)],
            "source_ip": f"10.0.{i // 256}.{i % 256}",
            "source_system": "mock",
        }
        for i in range(20)
    ]

    tasks = [test_client.post("/alerts/", json=alert) for alert in alerts]
    responses = await asyncio.gather(*tasks)

    # All should be accepted
    assert all(r.status_code == 202 for r in responses)


@pytest.mark.asyncio
async def test_concurrent_incident_queries(test_client: AsyncClient):
    """Test: System handles concurrent list/detail queries."""
    # First, create some incidents
    for i in range(10):
        await test_client.post(
            "/alerts/",
            json={
                "alert_type": "phishing",
                "severity": "high",
                "source_ip": f"192.168.1.{i}",
                "source_system": "mock",
            },
        )

    # Then query incidents concurrently
    tasks = [
        test_client.get("/incidents/"),
        test_client.get("/incidents/"),
        test_client.get("/incidents/"),
        test_client.get("/playbooks/"),
        test_client.get("/analytics/summary"),
        test_client.get("/health/"),
    ]
    responses = await asyncio.gather(*tasks)

    # All should succeed
    assert all(r.status_code == 200 for r in responses)
