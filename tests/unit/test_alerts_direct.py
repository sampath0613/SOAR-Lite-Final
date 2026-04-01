"""Direct unit tests for alert ingestion handler branches."""

import json

import pytest
from fastapi import HTTPException

from soar.api.alerts import ingest_alert
from soar.main import APP_STATE
from soar.models.playbook import Condition, Playbook, Step


@pytest.mark.asyncio
async def test_ingest_alert_without_source_system_returns_400(test_db):
    """Missing source_system should raise a 400 HTTPException."""
    with pytest.raises(HTTPException) as exc_info:
        await ingest_alert(alert_data={"alert_type": "phishing"}, db=test_db)

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_ingest_alert_without_playbooks_returns_503(test_db):
    """When no playbooks are loaded, ingestion should return 503."""
    original_playbooks = APP_STATE.get("playbooks", {})
    APP_STATE["playbooks"] = {}

    try:
        with pytest.raises(HTTPException) as exc_info:
            await ingest_alert(
                alert_data={
                    "source_system": "mock",
                    "alert_type": "phishing",
                    "severity": "high",
                    "source_ip": "1.1.1.1",
                },
                db=test_db,
            )
    finally:
        APP_STATE["playbooks"] = original_playbooks

    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_ingest_alert_unknown_source_system_returns_400(test_db):
    """Unknown source systems should be mapped to validation errors."""
    original_playbooks = APP_STATE.get("playbooks", {})
    APP_STATE["playbooks"] = {
        "pb": Playbook(
            name="pb",
            trigger_alert_type="phishing",
            min_severity="low",
            steps=[
                Step(
                    id="s1",
                    connector="mock_jira",
                    input_field="source_ip",
                    timeout=1,
                    retries=1,
                    on_result=[Condition(if_expr=None, then="continue")],
                )
            ],
        )
    }

    try:
        with pytest.raises(HTTPException) as exc_info:
            await ingest_alert(
                alert_data={
                    "source_system": "unknown_system",
                    "alert_type": "phishing",
                    "severity": "high",
                    "source_ip": "8.8.8.8",
                },
                db=test_db,
            )
    finally:
        APP_STATE["playbooks"] = original_playbooks

    assert exc_info.value.status_code == 400
    assert "Invalid alert" in exc_info.value.detail


@pytest.mark.asyncio
async def test_ingest_alert_internal_error_returns_500(test_db, monkeypatch):
    """Unexpected storage/runtime errors should be translated to 500."""
    original_playbooks = APP_STATE.get("playbooks", {})
    APP_STATE["playbooks"] = {
        "pb": Playbook(
            name="pb",
            trigger_alert_type="phishing",
            min_severity="low",
            steps=[
                Step(
                    id="s1",
                    connector="mock_jira",
                    input_field="source_ip",
                    timeout=1,
                    retries=1,
                    on_result=[Condition(if_expr=None, then="continue")],
                )
            ],
        )
    }

    async def _raise_error(*_args, **_kwargs):
        raise RuntimeError("db write failed")

    monkeypatch.setattr("soar.api.alerts.create_incident", _raise_error)

    try:
        with pytest.raises(HTTPException) as exc_info:
            await ingest_alert(
                alert_data={
                    "source_system": "mock",
                    "alert_type": "phishing",
                    "severity": "high",
                    "source_ip": "8.8.4.4",
                    "raw_payload": json.dumps({"test": True}),
                },
                db=test_db,
            )
    finally:
        APP_STATE["playbooks"] = original_playbooks

    assert exc_info.value.status_code == 500
