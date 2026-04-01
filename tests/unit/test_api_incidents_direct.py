"""Direct unit tests for incident API handlers."""

import json

import pytest
from fastapi import HTTPException

from soar.api.incidents import (
    get_incident_detail,
    list_incidents_endpoint,
    update_verdict,
)
from soar.db.crud import (
    create_incident,
    create_step_execution,
    update_step_execution,
)


@pytest.mark.asyncio
async def test_list_incidents_handles_invalid_alert_json(test_db):
    """List endpoint should tolerate malformed stored alert JSON."""
    await create_incident(
        test_db,
        alert_id="bad-json-1",
        playbook_name="phishing_triage",
        raw_alert_json="{not-valid-json",
    )

    payload = await list_incidents_endpoint(
        status_filter=None,
        page=1,
        page_size=20,
        db=test_db,
    )

    assert payload["total"] >= 1
    assert payload["incidents"][0]["severity"] == "unknown"


@pytest.mark.asyncio
async def test_list_incidents_invalid_status_returns_500(test_db):
    """Invalid status filters should return API-level 500 error payload."""
    with pytest.raises(HTTPException) as exc_info:
        await list_incidents_endpoint(
            status_filter="not_a_status",
            page=1,
            page_size=20,
            db=test_db,
        )

    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_get_incident_detail_handles_invalid_result_json(test_db):
    """Detail endpoint should handle malformed step result JSON safely."""
    incident = await create_incident(
        test_db,
        alert_id="incident-detail-1",
        playbook_name="phishing_triage",
        raw_alert_json=json.dumps({"severity": "high"}),
    )
    step = await create_step_execution(
        test_db,
        incident_id=incident.id,
        step_id="step-bad-result",
        connector_name="mock_jira",
        input_params_json=json.dumps({"k": "v"}),
    )
    await update_step_execution(
        test_db,
        step_execution_id=step.id,
        status="completed",
        result_json="{bad-json",
    )

    payload = await get_incident_detail(incident.id, db=test_db)

    assert payload["id"] == incident.id
    assert payload["steps"][0]["result"] == {}


@pytest.mark.asyncio
async def test_get_incident_detail_not_found_returns_404(test_db):
    """Missing incident IDs should return 404 from detail handler."""
    with pytest.raises(HTTPException) as exc_info:
        await get_incident_detail("missing-id", db=test_db)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_update_verdict_invalid_payload_returns_400(test_db):
    """Verdict handler should reject invalid verdict values."""
    with pytest.raises(HTTPException) as exc_info:
        await update_verdict(
            "any-id",
            verdict_data={"verdict": "bad_value"},
            db=test_db,
        )

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_update_verdict_not_found_maps_to_400(test_db):
    """Not-found incidents are converted to API-friendly 400 errors."""
    with pytest.raises(HTTPException) as exc_info:
        await update_verdict(
            "missing-id",
            verdict_data={"verdict": "true_positive"},
            db=test_db,
        )

    assert exc_info.value.status_code == 400
