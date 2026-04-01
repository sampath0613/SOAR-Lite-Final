"""Integration tests for detailed analytics summary behavior."""

import json

import pytest

from soar.db.crud import (
    create_incident,
    create_step_execution,
    update_incident_status,
    update_incident_verdict,
)


@pytest.mark.asyncio
async def test_analytics_summary_counts_rates_and_connector_stats(test_client, test_db):
    """Summary endpoint should compute status breakdown, rates, and connector stats."""
    completed = await create_incident(
        test_db,
        alert_id="analytics-1",
        playbook_name="phishing_triage",
        raw_alert_json=json.dumps({"test": True}),
    )
    await create_step_execution(
        test_db,
        incident_id=completed.id,
        step_id="test_step_1",
        connector_name="mock_jira",
        status="completed",
        input_data={"key": "value"},
        result_data={"ok": True},
    )
    await update_incident_status(test_db, completed.id, "completed")
    await update_incident_verdict(test_db, completed.id, "true_positive")

    failed = await create_incident(
        test_db,
        alert_id="analytics-2",
        playbook_name="phishing_triage",
        raw_alert_json=json.dumps({"test": True}),
    )
    await create_step_execution(
        test_db,
        incident_id=failed.id,
        step_id="test_step_2",
        connector_name="mock_jira",
        status="failed",
        input_data={"key": "value"},
        result_data={"ok": False},
    )
    await update_incident_status(test_db, failed.id, "failed")
    await update_incident_verdict(test_db, failed.id, "false_positive")

    response = await test_client.get("/analytics/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_incidents"] >= 2
    assert payload["by_status"]["completed"] >= 1
    assert payload["by_status"]["failed"] >= 1
    assert payload["false_positive_rate"] >= 0
    assert "mock_jira" in payload["connector_error_rates"]
