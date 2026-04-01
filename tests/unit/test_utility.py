"""Unit tests for step utility scoring."""

import json

import pytest

from soar.analytics.utility import compute_step_utility, recompute_playbook_metrics
from soar.db.crud import create_incident, create_step_execution, update_incident_verdict
from soar.main import APP_STATE


@pytest.mark.asyncio
async def test_compute_step_utility_no_verdicts(test_db):
    """Returns neutral score when no verdicted incidents exist."""
    utility = await compute_step_utility("test_playbook", "step1", test_db)
    assert utility == 0.5


@pytest.mark.asyncio
async def test_compute_step_utility_all_true_positives(test_db):
    """Returns 1.0 when every verdicted execution is true positive."""
    for i in range(3):
        incident = await create_incident(
            test_db,
            alert_id=f"alert_{i}",
            playbook_name="test_playbook",
            raw_alert_json=json.dumps({"test": True}),
        )
        await create_step_execution(
            test_db,
            incident_id=incident.id,
            step_id="step1",
            connector_name="mock_jira",
            input_params_json=json.dumps({"key": "value"}),
        )
        await update_incident_verdict(test_db, incident.id, "true_positive")

    utility = await compute_step_utility("test_playbook", "step1", test_db)
    assert utility == 1.0


@pytest.mark.asyncio
async def test_compute_step_utility_all_false_positives(test_db):
    """Returns 0.0 when every verdicted execution is false positive."""
    for i in range(3):
        incident = await create_incident(
            test_db,
            alert_id=f"alert_{i}",
            playbook_name="test_playbook",
            raw_alert_json=json.dumps({"test": True}),
        )
        await create_step_execution(
            test_db,
            incident_id=incident.id,
            step_id="step1",
            connector_name="mock_jira",
            status="completed",
            input_data={"key": "value"},
            result_data={"ticket_id": "SOAR-1234"},
        )
        await update_incident_verdict(test_db, incident.id, "false_positive")

    utility = await compute_step_utility("test_playbook", "step1", test_db)
    assert utility == 0.0


@pytest.mark.asyncio
async def test_compute_step_utility_mixed_verdicts(test_db):
    """Computes ratio correctly with mixed verdict outcomes."""
    for i in range(2):
        incident = await create_incident(
            test_db,
            alert_id=f"true_alert_{i}",
            playbook_name="test_playbook",
            raw_alert_json=json.dumps({"test": True}),
        )
        await create_step_execution(
            test_db,
            incident_id=incident.id,
            step_id="step1",
            connector_name="mock_jira",
            input_params_json=json.dumps({"key": "value"}),
        )
        await update_incident_verdict(test_db, incident.id, "true_positive")

    for i in range(2):
        incident = await create_incident(
            test_db,
            alert_id=f"false_alert_{i}",
            playbook_name="test_playbook",
            raw_alert_json=json.dumps({"test": True}),
        )
        await create_step_execution(
            test_db,
            incident_id=incident.id,
            step_id="step1",
            connector_name="mock_jira",
            input_params_json=json.dumps({"key": "value"}),
        )
        await update_incident_verdict(test_db, incident.id, "false_positive")

    utility = await compute_step_utility("test_playbook", "step1", test_db)
    assert utility == 0.5


@pytest.mark.asyncio
async def test_compute_step_utility_ignores_incidents_without_verdict(test_db):
    """Incidents without analyst verdict must be ignored."""
    for i in range(2):
        incident = await create_incident(
            test_db,
            alert_id=f"alert_{i}",
            playbook_name="test_playbook",
            raw_alert_json=json.dumps({"test": True}),
        )
        await create_step_execution(
            test_db,
            incident_id=incident.id,
            step_id="step1",
            connector_name="mock_jira",
            input_params_json=json.dumps({"key": "value"}),
        )
        await update_incident_verdict(test_db, incident.id, "true_positive")

    no_verdict_incident = await create_incident(
        test_db,
        alert_id="alert_no_verdict",
        playbook_name="test_playbook",
        raw_alert_json=json.dumps({"test": True}),
    )
    await create_step_execution(
        test_db,
        incident_id=no_verdict_incident.id,
        step_id="step1",
        connector_name="mock_jira",
        input_params_json=json.dumps({"key": "value"}),
    )

    utility = await compute_step_utility("test_playbook", "step1", test_db)
    assert utility == 1.0


@pytest.mark.asyncio
async def test_compute_step_utility_isolated_by_step_and_playbook(test_db):
    """Scoring should be scoped by both playbook and step ID."""
    first = await create_incident(
        test_db,
        alert_id="alert_1",
        playbook_name="playbook1",
        raw_alert_json=json.dumps({"test": True}),
    )
    await create_step_execution(
        test_db,
        incident_id=first.id,
        step_id="step_a",
        connector_name="mock_jira",
        input_params_json=json.dumps({"key": "value"}),
    )
    await update_incident_verdict(test_db, first.id, "true_positive")

    second = await create_incident(
        test_db,
        alert_id="alert_2",
        playbook_name="playbook2",
        raw_alert_json=json.dumps({"test": True}),
    )
    await create_step_execution(
        test_db,
        incident_id=second.id,
        step_id="step_a",
        connector_name="mock_jira",
        input_params_json=json.dumps({"key": "value"}),
    )
    await update_incident_verdict(test_db, second.id, "false_positive")

    utility_a = await compute_step_utility("playbook1", "step_a", test_db)
    assert utility_a == 1.0

    utility_other = await compute_step_utility("playbook2", "step_a", test_db)
    assert utility_other == 0.0


@pytest.mark.asyncio
async def test_recompute_playbook_metrics_playbook_not_found(test_db):
    """Recompute returns empty result when playbook is not loaded in app state."""
    original = APP_STATE.get("playbooks", {})
    APP_STATE["playbooks"] = {}
    try:
        result = await recompute_playbook_metrics("missing", test_db)
        assert result == {}
    finally:
        APP_STATE["playbooks"] = original


@pytest.mark.asyncio
async def test_recompute_playbook_metrics_for_loaded_playbook(test_db):
    """Recompute calculates utility per step for a loaded playbook."""

    class _Step:
        def __init__(self, step_id: str):
            self.id = step_id

    class _Playbook:
        def __init__(self):
            self.steps = [_Step("step1"), _Step("step2")]

    incident = await create_incident(
        test_db,
        alert_id="recompute_alert",
        playbook_name="recompute_pb",
        raw_alert_json=json.dumps({"test": True}),
    )
    await create_step_execution(
        test_db,
        incident_id=incident.id,
        step_id="step1",
        connector_name="mock_jira",
        input_params_json=json.dumps({"key": "value"}),
    )
    await update_incident_verdict(test_db, incident.id, "true_positive")

    original = APP_STATE.get("playbooks", {})
    APP_STATE["playbooks"] = {"recompute_pb": _Playbook()}
    try:
        result = await recompute_playbook_metrics("recompute_pb", test_db)
        assert set(result.keys()) == {"step1", "step2"}
        assert result["step1"] == 1.0
        assert result["step2"] == 0.5
    finally:
        APP_STATE["playbooks"] = original
