"""Unit tests for state machine transitions."""

import pytest

from soar.engine.state_machine import (
    IncidentState,
    StepState,
    StateTransitionError,
    is_valid_incident_transition,
    is_valid_step_transition,
    validate_incident_transition,
    validate_step_transition,
)


class TestIncidentStateTransitions:
    """Test incident status transition validation."""

    def test_pending_to_running_valid(self):
        """Test: PENDING → RUNNING is valid."""
        assert is_valid_incident_transition("pending", "running")

    def test_pending_to_completed_invalid(self):
        """Test: PENDING → COMPLETED is invalid (must go through RUNNING)."""
        assert not is_valid_incident_transition("pending", "completed")

    def test_running_to_completed_valid(self):
        """Test: RUNNING → COMPLETED is valid."""
        assert is_valid_incident_transition("running", "completed")

    def test_running_to_failed_valid(self):
        """Test: RUNNING → FAILED is valid."""
        assert is_valid_incident_transition("running", "failed")

    def test_running_to_escalated_valid(self):
        """Test: RUNNING → ESCALATED is valid."""
        assert is_valid_incident_transition("running", "escalated")

    def test_completed_to_running_invalid(self):
        """Test: COMPLETED → RUNNING is invalid (terminal state)."""
        assert not is_valid_incident_transition("completed", "running")

    def test_failed_to_completed_invalid(self):
        """Test: FAILED → COMPLETED is invalid (terminal state)."""
        assert not is_valid_incident_transition("failed", "completed")

    def test_escalated_to_running_invalid(self):
        """Test: ESCALATED → RUNNING is invalid (terminal state)."""
        assert not is_valid_incident_transition("escalated", "running")

    def test_validate_incident_transition_valid(self):
        """Test: validate_incident_transition() doesn't raise for valid transition."""
        # Should not raise
        validate_incident_transition("pending", "running")

    def test_validate_incident_transition_invalid(self):
        """Test: validate_incident_transition() raises StateTransitionError for invalid."""
        with pytest.raises(StateTransitionError) as exc_info:
            validate_incident_transition("completed", "running")

        assert "Invalid" in str(exc_info.value)


class TestStepStateTransitions:
    """Test step status transition validation."""

    def test_pending_to_running_valid(self):
        """Test: PENDING → RUNNING is valid."""
        assert is_valid_step_transition("pending", "running")

    def test_pending_to_completed_invalid(self):
        """Test: PENDING → COMPLETED is invalid (must go through RUNNING)."""
        assert not is_valid_step_transition("pending", "completed")

    def test_running_to_completed_valid(self):
        """Test: RUNNING → COMPLETED is valid."""
        assert is_valid_step_transition("running", "completed")

    def test_running_to_failed_valid(self):
        """Test: RUNNING → FAILED is valid."""
        assert is_valid_step_transition("running", "failed")

    def test_completed_to_running_invalid(self):
        """Test: COMPLETED → RUNNING is invalid (terminal state)."""
        assert not is_valid_step_transition("completed", "running")

    def test_failed_to_completed_invalid(self):
        """Test: FAILED → COMPLETED is invalid (terminal state)."""
        assert not is_valid_step_transition("failed", "completed")

    def test_validate_step_transition_valid(self):
        """Test: validate_step_transition() doesn't raise for valid transition."""
        # Should not raise
        validate_step_transition("pending", "running")

    def test_validate_step_transition_invalid(self):
        """Test: validate_step_transition() raises StateTransitionError for invalid."""
        with pytest.raises(StateTransitionError) as exc_info:
            validate_step_transition("completed", "running")

        assert "Invalid" in str(exc_info.value)


class TestStateEnum:
    """Test status enum values."""

    def test_incident_state_values(self):
        """Test: IncidentState has all required values."""
        assert hasattr(IncidentState, "PENDING")
        assert hasattr(IncidentState, "RUNNING")
        assert hasattr(IncidentState, "COMPLETED")
        assert hasattr(IncidentState, "FAILED")
        assert hasattr(IncidentState, "ESCALATED")

    def test_step_state_values(self):
        """Test: StepState has all required values."""
        assert hasattr(StepState, "PENDING")
        assert hasattr(StepState, "RUNNING")
        assert hasattr(StepState, "COMPLETED")
        assert hasattr(StepState, "FAILED")
