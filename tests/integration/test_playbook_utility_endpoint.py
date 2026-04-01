"""Integration tests for playbook utility endpoint."""

import json

import pytest

from soar.db.crud import create_incident, create_step_execution, update_incident_verdict


@pytest.mark.asyncio
async def test_get_step_utility_for_known_playbook(test_client, test_db):
    """Endpoint should return utility payload for each playbook step."""
    incident = await create_incident(
        test_db,
        alert_id="pb-utility-1",
        playbook_name="phishing_triage",
        raw_alert_json=json.dumps({"test": True}),
    )
    await create_step_execution(
        test_db,
        incident_id=incident.id,
        step_id="test_step_1",
        connector_name="mock_jira",
        input_params_json=json.dumps({"ip": "1.1.1.1"}),
    )
    await update_incident_verdict(test_db, incident.id, "false_positive")

    response = await test_client.get("/playbooks/phishing_triage/step-utility")

    assert response.status_code == 200
    data = response.json()
    assert data["playbook"] == "phishing_triage"
    assert len(data["steps"]) >= 1
    assert "utility_score" in data["steps"][0]
    assert "recommendation" in data["steps"][0]


@pytest.mark.asyncio
async def test_get_step_utility_unknown_playbook_returns_404(test_client):
    """Unknown playbook should return not found."""
    response = await test_client.get("/playbooks/does-not-exist/step-utility")

    assert response.status_code == 404
