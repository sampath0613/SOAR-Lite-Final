"""Unit tests for executor control flow and condition handling."""

import json

import pytest

from soar.connectors.base import ConnectorResult
from soar.db.crud import (
    create_incident,
    get_incident,
    get_step_executions_for_incident,
)
from soar.engine.executor import _evaluate_conditions, execute_playbook
from soar.models.alert import Alert
from soar.models.playbook import Condition, Playbook, Step


class _StubConnector:
    """Simple async connector stub for executor tests."""

    def __init__(self, data: dict):
        self._data = data

    async def execute(self, params: dict) -> ConnectorResult:
        return ConnectorResult(success=True, data=self._data)


@pytest.mark.asyncio
async def test_execute_playbook_success_flow(test_db, monkeypatch):
    """Executor should mark incident completed when steps continue and finish."""
    incident = await create_incident(
        test_db,
        alert_id="exec-success-1",
        playbook_name="unit_exec_success",
        raw_alert_json=json.dumps({"test": True}),
    )

    playbook = Playbook(
        name="unit_exec_success",
        trigger_alert_type="phishing",
        min_severity="low",
        steps=[
            Step(
                id="step_one",
                connector="stub",
                input_field="source_ip",
                timeout=2,
                retries=1,
                on_result=[Condition(if_expr=None, then="continue")],
            )
        ],
    )
    alert = Alert(
        alert_id="alert-exec-success-1",
        alert_type="phishing",
        severity="high",
        source_ip="1.2.3.4",
        destination_ip="10.0.0.1",
        source_system="mock",
    )

    monkeypatch.setattr(
        "soar.engine.executor.get_connector",
        lambda _name: _StubConnector({"score": 10}),
    )

    await execute_playbook(incident.id, playbook, alert, test_db)

    updated = await get_incident(test_db, incident.id)
    assert updated is not None
    assert updated.status.value == "completed"

    steps = await get_step_executions_for_incident(test_db, incident.id)
    assert len(steps) == 1
    assert steps[0].status.value == "completed"


@pytest.mark.asyncio
async def test_execute_playbook_escalates_on_condition(test_db, monkeypatch):
    """Executor should escalate when on_result expression evaluates true."""
    incident = await create_incident(
        test_db,
        alert_id="exec-escalate-1",
        playbook_name="unit_exec_escalate",
        raw_alert_json=json.dumps({"test": True}),
    )

    playbook = Playbook(
        name="unit_exec_escalate",
        trigger_alert_type="phishing",
        min_severity="low",
        steps=[
            Step(
                id="step_escalate",
                connector="stub",
                input_field="source_ip",
                timeout=2,
                retries=1,
                on_result=[
                    Condition(if_expr="score > 70", then="escalate"),
                    Condition(if_expr=None, then="continue"),
                ],
            )
        ],
    )
    alert = Alert(
        alert_id="alert-exec-escalate-1",
        alert_type="phishing",
        severity="high",
        source_ip="5.6.7.8",
        destination_ip="10.0.0.2",
        source_system="mock",
    )

    monkeypatch.setattr(
        "soar.engine.executor.get_connector",
        lambda _name: _StubConnector({"score": 99}),
    )

    await execute_playbook(incident.id, playbook, alert, test_db)

    updated = await get_incident(test_db, incident.id)
    assert updated is not None
    assert updated.status.value == "escalated"


@pytest.mark.asyncio
async def test_execute_playbook_handles_missing_alert_field(test_db, monkeypatch):
    """Missing playbook input field should fail execution and end in failed state."""
    incident = await create_incident(
        test_db,
        alert_id="exec-missing-field-1",
        playbook_name="unit_exec_missing",
        raw_alert_json=json.dumps({"test": True}),
    )

    playbook = Playbook(
        name="unit_exec_missing",
        trigger_alert_type="phishing",
        min_severity="low",
        steps=[
            Step(
                id="step_missing",
                connector="stub",
                input_field="nonexistent_field",
                timeout=2,
                retries=1,
                on_result=[Condition(if_expr=None, then="continue")],
            )
        ],
    )
    alert = Alert(
        alert_id="alert-exec-missing-1",
        alert_type="phishing",
        severity="high",
        source_ip="9.9.9.9",
        destination_ip="10.0.0.3",
        source_system="mock",
    )

    monkeypatch.setattr(
        "soar.engine.executor.get_connector",
        lambda _name: _StubConnector({"score": 1}),
    )

    await execute_playbook(incident.id, playbook, alert, test_db)

    updated = await get_incident(test_db, incident.id)
    assert updated is not None
    assert updated.status.value == "failed"


@pytest.mark.asyncio
async def test_evaluate_conditions_no_match_keeps_status(test_db):
    """If no condition matches, executor should leave incident status unchanged."""
    incident = await create_incident(
        test_db,
        alert_id="exec-no-match-1",
        playbook_name="unit_exec_no_match",
        raw_alert_json=json.dumps({"test": True}),
    )

    await _evaluate_conditions(
        incident_id=incident.id,
        step_id="step_warn",
        conditions=[Condition(if_expr="score > 100", then="escalate")],
        result_data={"score": 1},
        db=test_db,
    )

    updated = await get_incident(test_db, incident.id)
    assert updated is not None
    assert updated.status.value == "pending"
