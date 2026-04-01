"""
State machine for incident and step execution status transitions.
Enforces valid state transitions and prevents invalid operations.
"""

import logging
from enum import Enum

logger = logging.getLogger(__name__)


class IncidentState(str, Enum):
    """Incident execution state."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ESCALATED = "escalated"


class StepState(str, Enum):
    """Step execution state."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class StateTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""

    pass


# Valid incident transitions: from_state -> allowed_to_states
INCIDENT_TRANSITIONS = {
    IncidentState.PENDING: {IncidentState.RUNNING},
    IncidentState.RUNNING: {
        IncidentState.COMPLETED,
        IncidentState.FAILED,
        IncidentState.ESCALATED,
    },
    IncidentState.COMPLETED: set(),  # Terminal state
    IncidentState.FAILED: set(),  # Terminal state
    IncidentState.ESCALATED: set(),  # Terminal state
}

# Valid step transitions: from_state -> allowed_to_states
STEP_TRANSITIONS = {
    StepState.PENDING: {StepState.RUNNING},
    StepState.RUNNING: {StepState.COMPLETED, StepState.FAILED},
    StepState.COMPLETED: set(),  # Terminal state
    StepState.FAILED: set(),  # Terminal state
}


def is_valid_incident_transition(from_state: str, to_state: str) -> bool:
    """
    Check if an incident state transition is valid.

    Args:
        from_state: Current state (string)
        to_state: Target state (string)

    Returns:
        True if transition is valid, False otherwise
    """
    try:
        from_state_enum = IncidentState(from_state)
        to_state_enum = IncidentState(to_state)
    except ValueError:
        return False

    allowed_transitions = INCIDENT_TRANSITIONS.get(from_state_enum, set())
    return to_state_enum in allowed_transitions


def is_valid_step_transition(from_state: str, to_state: str) -> bool:
    """
    Check if a step state transition is valid.

    Args:
        from_state: Current state (string)
        to_state: Target state (string)

    Returns:
        True if transition is valid, False otherwise
    """
    try:
        from_state_enum = StepState(from_state)
        to_state_enum = StepState(to_state)
    except ValueError:
        return False

    allowed_transitions = STEP_TRANSITIONS.get(from_state_enum, set())
    return to_state_enum in allowed_transitions


def validate_incident_transition(from_state: str, to_state: str) -> None:
    """
    Validate an incident state transition, raising error if invalid.

    Args:
        from_state: Current state (string)
        to_state: Target state (string)

    Raises:
        StateTransitionError: If transition is invalid
    """
    if not is_valid_incident_transition(from_state, to_state):
        allowed = INCIDENT_TRANSITIONS.get(IncidentState(from_state), set())
        allowed_str = ", ".join([s.value for s in allowed]) or "none (terminal state)"
        raise StateTransitionError(
            f"Invalid incident transition: {from_state} -> {to_state}. "
            f"Allowed transitions: {allowed_str}"
        )


def validate_step_transition(from_state: str, to_state: str) -> None:
    """
    Validate a step state transition, raising error if invalid.

    Args:
        from_state: Current state (string)
        to_state: Target state (string)

    Raises:
        StateTransitionError: If transition is invalid
    """
    if not is_valid_step_transition(from_state, to_state):
        allowed = STEP_TRANSITIONS.get(StepState(from_state), set())
        allowed_str = ", ".join([s.value for s in allowed]) or "none (terminal state)"
        raise StateTransitionError(
            f"Invalid step transition: {from_state} -> {to_state}. "
            f"Allowed transitions: {allowed_str}"
        )
