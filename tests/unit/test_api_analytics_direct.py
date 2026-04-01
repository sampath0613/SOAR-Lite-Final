"""Direct unit tests for analytics API handler."""

import json

import pytest

from soar.api.analytics import get_summary
from soar.db.crud import (
    create_incident,
    create_step_execution,
    update_incident_status,
    update_incident_verdict,
)


@pytest.mark.asyncio
async def test_get_summary_empty_dataset(test_db):
    """Summary should return stable zeroed metrics with no incidents."""
    payload = await get_summary(db=test_db)

    assert payload["total_incidents"] == 0
    assert payload["false_positive_rate"] == 0
    assert payload["connector_error_rates"] == {}


@pytest.mark.asyncio
async def test_get_summary_with_completed_and_failed_incidents(test_db):
    """Summary should compute status, FP rate, and per-connector error metrics."""
    incident_ok = await create_incident(
        test_db,
        alert_id="sum-1",
        playbook_name="phishing_triage",
        raw_alert_json=json.dumps({"test": True}),
    )
    await create_step_execution(
        test_db,
        incident_id=incident_ok.id,
        step_id="step_ok",
        connector_name="mock_jira",
        status="completed",
        input_data={"k": "v"},
        result_data={"ok": True},
    )
    await update_incident_status(test_db, incident_ok.id, "completed")
    await update_incident_verdict(test_db, incident_ok.id, "true_positive")

    incident_bad = await create_incident(
        test_db,
        alert_id="sum-2",
        playbook_name="phishing_triage",
        raw_alert_json=json.dumps({"test": True}),
    )
    await create_step_execution(
        test_db,
        incident_id=incident_bad.id,
        step_id="step_bad",
        connector_name="mock_jira",
        status="failed",
        input_data={"k": "v"},
        result_data={"ok": False},
    )
    await update_incident_status(test_db, incident_bad.id, "failed")
    await update_incident_verdict(test_db, incident_bad.id, "false_positive")

    payload = await get_summary(db=test_db)

    assert payload["total_incidents"] >= 2
    assert payload["by_status"]["completed"] >= 1
    assert payload["by_status"]["failed"] >= 1
    assert payload["false_positive_rate"] == 0.5
    assert payload["avg_resolution_time_seconds"] >= 0

    connector = payload["connector_error_rates"]["mock_jira"]
    assert connector["total_executions"] >= 2
    assert connector["failed"] >= 1
    assert connector["error_rate"] >= 0
