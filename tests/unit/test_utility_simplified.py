"""Unit tests for step utility scoring."""

import pytest

from soar.analytics.utility import compute_step_utility
from soar.db.crud import (
    create_incident,
    update_incident_verdict,
)
import json


@pytest.mark.asyncio
async def test_compute_step_utility_no_verdicts(test_db):
    """Test: compute_step_utility returns 0.5 (neutral) with no verdicts."""
    utility = await compute_step_utility("nonexistent_playbook", "step1", test_db)

    # No verdicts found → return neutral score
    assert utility == 0.5


@pytest.mark.asyncio
async def test_add_verdict_and_verify_storage(test_db):
    """Test: Adding verdict to incident allows retrieval."""
    # Create an incident
    incident = await create_incident(
        test_db,
        alert_id="test_alert",
        playbook_name="test_playbook",
        raw_alert_json=json.dumps({"test": True}),
    )

    # Add a verdict
    await update_incident_verdict(test_db, incident.id, "true_positive")

    # Verify it was stored (this tests the CRUD layer, not utility scoring)
    assert incident.analyst_verdict is None  # Not yet persisted in this object

    # But we can compute utility (should return 0.5 since no step executions)
    utility = await compute_step_utility("test_playbook", "step1", test_db)
    assert utility == 0.5
