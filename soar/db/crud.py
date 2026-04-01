"""
CRUD (Create, Read, Update, Delete) operations for the database.
All database writes go through this module only.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple

from sqlalchemy import select, func, desc, update
from sqlalchemy.ext.asyncio import AsyncSession

from soar.models.incident import (
    Incident,
    StepExecution,
    PlaybookMetrics,
    IncidentStatus,
    StepStatus,
)

logger = logging.getLogger(__name__)


def _normalize_incident_status(value: str | IncidentStatus) -> IncidentStatus:
    """Normalize flexible incident status input to IncidentStatus enum."""
    if isinstance(value, IncidentStatus):
        return value

    cleaned = str(value).strip()
    if cleaned.startswith("IncidentStatus."):
        cleaned = cleaned.split(".", 1)[1]

    try:
        return IncidentStatus(cleaned.lower())
    except ValueError:
        try:
            return IncidentStatus[cleaned.upper()]
        except KeyError as error:
            raise ValueError(f"Invalid incident status: {value}") from error


def _normalize_step_status(value: str | StepStatus) -> StepStatus:
    """Normalize flexible step status input to StepStatus enum."""
    if isinstance(value, StepStatus):
        return value

    cleaned = str(value).strip()
    if cleaned.startswith("StepStatus."):
        cleaned = cleaned.split(".", 1)[1]

    try:
        return StepStatus(cleaned.lower())
    except ValueError:
        try:
            return StepStatus[cleaned.upper()]
        except KeyError as error:
            raise ValueError(f"Invalid step status: {value}") from error


# ============================================================================
# INCIDENT Operations
# ============================================================================


async def create_incident(
    db: AsyncSession,
    alert_id: str,
    playbook_name: str,
    raw_alert_json: str,
) -> Incident:
    """
    Create a new incident record.

    Args:
        db: AsyncSession
        alert_id: Unique alert identifier
        playbook_name: Name of playbook to execute
        raw_alert_json: Stringified JSON of the alert

    Returns:
        Created Incident instance
    """
    incident = Incident(
        alert_id=alert_id,
        playbook_name=playbook_name,
        status=IncidentStatus.PENDING,
        raw_alert_json=raw_alert_json,
    )
    db.add(incident)
    await db.commit()
    logger.info(
        f"Created incident {incident.id} for alert {alert_id} "
        f"with playbook {playbook_name}"
    )
    return incident


async def get_incident(
    db: AsyncSession,
    incident_id: str,
) -> Optional[Incident]:
    """
    Fetch a single incident by ID.

    Args:
        db: AsyncSession
        incident_id: Incident UUID

    Returns:
        Incident or None if not found
    """
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    return result.unique().scalar_one_or_none()


async def list_incidents(
    db: AsyncSession,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[list[Incident], int]:
    """
    List incidents with optional filtering and pagination.

    Args:
        db: AsyncSession
        status: Optional status filter (IncidentStatus enum value)
        page: Page number (1-indexed)
        page_size: Items per page

    Returns:
        Tuple of (incident list, total count)
    """
    query = select(Incident)
    normalized_status = None

    if status:
        normalized_status = _normalize_incident_status(status)
        query = query.where(Incident.status == normalized_status)

    # Get total count
    count_query = select(func.count()).select_from(Incident)
    if normalized_status:
        count_query = count_query.where(Incident.status == normalized_status)

    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    # Add ordering and pagination
    query = query.order_by(desc(Incident.created_at))
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    incidents = result.unique().scalars().all()

    return list(incidents), total_count


async def update_incident_status(
    db: AsyncSession,
    incident_id: str,
    new_status: str | IncidentStatus,
) -> Incident:
    """
    Update incident status.

    Args:
        db: AsyncSession
        incident_id: Incident UUID
        new_status: New status (IncidentStatus enum value)

    Returns:
        Updated Incident

    Raises:
        ValueError: If incident not found
    """
    incident = await get_incident(db, incident_id)
    if not incident:
        raise ValueError(f"Incident {incident_id} not found")

    normalized_status = _normalize_incident_status(new_status)
    incident.status = normalized_status

    # Set resolved_at if transitioning to terminal state
    if normalized_status in [
        IncidentStatus.COMPLETED,
        IncidentStatus.FAILED,
        IncidentStatus.ESCALATED,
    ]:
        incident.resolved_at = datetime.now(timezone.utc)

    await db.commit()
    logger.info(f"Updated incident {incident_id} status to {normalized_status.value}")
    return incident


async def update_incident_verdict(
    db: AsyncSession,
    incident_id: str,
    verdict: str,
) -> Incident:
    """
    Update analyst verdict for an incident (true_positive or false_positive).

    Args:
        db: AsyncSession
        incident_id: Incident UUID
        verdict: "true_positive" or "false_positive"

    Returns:
        Updated Incident

    Raises:
        ValueError: If incident not found or invalid verdict
    """
    if verdict not in ["true_positive", "false_positive"]:
        raise ValueError(f"Invalid verdict: {verdict}")

    result = await db.execute(select(Incident.id).where(Incident.id == incident_id))
    if result.scalar_one_or_none() is None:
        raise ValueError(f"Incident {incident_id} not found")

    await db.execute(
        update(Incident)
        .where(Incident.id == incident_id)
        .values(analyst_verdict=verdict)
        .execution_options(synchronize_session=False)
    )
    await db.commit()

    # Clear identity map so callers holding a previously loaded Incident object
    # do not get in-session auto-refresh side effects.
    db.expunge_all()

    incident = await get_incident(db, incident_id)
    logger.info(f"Set incident {incident_id} verdict to {verdict}")
    return incident


# ============================================================================
# STEP EXECUTION Operations
# ============================================================================


async def create_step_execution(
    db: AsyncSession,
    incident_id: str,
    step_id: str,
    connector_name: str,
    input_params_json: Optional[str] = None,
    status: Optional[str] = None,
    input_data: Optional[dict] = None,
    result_data: Optional[dict] = None,
    attempt_number: int = 1,
) -> StepExecution:
    """
    Create a new step execution record.

    Args:
        db: AsyncSession
        incident_id: Parent incident UUID
        step_id: Step ID from playbook
        connector_name: Connector name to execute
        input_params_json: Optional pre-serialized input JSON
        status: Optional initial step status (defaults to pending)
        input_data: Optional input dict; serialized when input_params_json not provided
        result_data: Optional result dict; serialized to result_json if provided
        attempt_number: Initial attempt number

    Returns:
        Created StepExecution instance
    """
    if input_params_json is None:
        input_params_json = json.dumps(input_data or {})

    parsed_status = _normalize_step_status(status or StepStatus.PENDING)

    step_exec = StepExecution(
        incident_id=incident_id,
        step_id=step_id,
        connector_name=connector_name,
        status=parsed_status,
        input_params_json=input_params_json,
        result_json=json.dumps(result_data) if result_data is not None else None,
        attempt_number=attempt_number,
    )
    db.add(step_exec)
    await db.commit()
    logger.debug(
        f"Created step_execution {step_exec.id} for incident {incident_id} "
        f"step {step_id} via {connector_name}"
    )
    return step_exec


async def get_step_execution(
    db: AsyncSession,
    step_execution_id: str,
) -> Optional[StepExecution]:
    """Fetch a single step execution by ID."""
    result = await db.execute(
        select(StepExecution).where(StepExecution.id == step_execution_id)
    )
    return result.scalar_one_or_none()


async def update_step_execution(
    db: AsyncSession,
    step_execution_id: str,
    status: str | StepStatus,
    result_json: Optional[str] = None,
    completed_at: Optional[datetime] = None,
    attempt_number: Optional[int] = None,
) -> StepExecution:
    """
    Update step execution status and result.

    Args:
        db: AsyncSession
        step_execution_id: StepExecution UUID
        status: New status (StepStatus enum value)
        result_json: Optional result JSON string
        completed_at: Optional completion timestamp
        attempt_number: Optional attempt counter

    Returns:
        Updated StepExecution

    Raises:
        ValueError: If step_execution not found
    """
    step_exec = await get_step_execution(db, step_execution_id)
    if not step_exec:
        raise ValueError(f"StepExecution {step_execution_id} not found")

    step_exec.status = _normalize_step_status(status)
    if result_json is not None:
        step_exec.result_json = result_json
    if completed_at is not None:
        step_exec.completed_at = completed_at
    if attempt_number is not None:
        step_exec.attempt_number = attempt_number

    await db.commit()
    logger.debug(f"Updated step_execution {step_execution_id} status to {status}")
    return step_exec


async def get_step_executions_for_incident(
    db: AsyncSession,
    incident_id: str,
) -> list[StepExecution]:
    """
    Fetch all step executions for an incident, ordered chronologically.

    Args:
        db: AsyncSession
        incident_id: Parent incident UUID

    Returns:
        List of StepExecution ordered by started_at
    """
    result = await db.execute(
        select(StepExecution)
        .where(StepExecution.incident_id == incident_id)
        .order_by(StepExecution.started_at)
    )
    return list(result.scalars().all())


async def get_step_executions_for_playbook_step(
    db: AsyncSession,
    playbook_name: str,
    step_id: str,
) -> list[StepExecution]:
    """
    Fetch all step executions for a specific step across all incidents.
    Used for utility score computation.

    Args:
        db: AsyncSession
        playbook_name: Playbook name
        step_id: Step ID

    Returns:
        List of StepExecution joined with parent incident data
    """
    result = await db.execute(
        select(StepExecution)
        .join(Incident, StepExecution.incident_id == Incident.id)
        .where(
            (Incident.playbook_name == playbook_name) & (StepExecution.step_id == step_id)
        )
        .order_by(StepExecution.started_at)
    )
    return list(result.scalars().all())


# ============================================================================
# PLAYBOOK METRICS Operations
# ============================================================================


async def upsert_playbook_metrics(
    db: AsyncSession,
    playbook_name: str,
    step_id: str,
    execution_count: int,
    verdict_changed_count: int,
) -> PlaybookMetrics:
    """
    Create or update playbook metrics for a step.

    Args:
        db: AsyncSession
        playbook_name: Playbook name
        step_id: Step ID
        execution_count: Total executions
        verdict_changed_count: Verdicts that changed

    Returns:
        Created or updated PlaybookMetrics
    """
    result = await db.execute(
        select(PlaybookMetrics).where(
            (PlaybookMetrics.playbook_name == playbook_name)
            & (PlaybookMetrics.step_id == step_id)
        )
    )
    metrics = result.scalar_one_or_none()

    if metrics:
        metrics.execution_count = execution_count
        metrics.verdict_changed_count = verdict_changed_count
        metrics.last_computed_at = datetime.now(timezone.utc)
    else:
        metrics = PlaybookMetrics(
            playbook_name=playbook_name,
            step_id=step_id,
            execution_count=execution_count,
            verdict_changed_count=verdict_changed_count,
        )
        db.add(metrics)

    await db.commit()
    logger.debug(
        f"Upserted metric for {playbook_name}/{step_id}: "
        f"executions={execution_count}, verdicts={verdict_changed_count}"
    )
    return metrics


async def get_playbook_metrics(
    db: AsyncSession,
    playbook_name: str,
    step_id: Optional[str] = None,
) -> Optional[PlaybookMetrics] | list[PlaybookMetrics]:
    """
    Fetch playbook metrics.

    Args:
        db: AsyncSession
        playbook_name: Playbook name
        step_id: Optional specific step ID

    Returns:
        PlaybookMetrics, list of PlaybookMetrics, or None
    """
    if step_id:
        result = await db.execute(
            select(PlaybookMetrics).where(
                (PlaybookMetrics.playbook_name == playbook_name)
                & (PlaybookMetrics.step_id == step_id)
            )
        )
        return result.scalar_one_or_none()
    else:
        result = await db.execute(
            select(PlaybookMetrics).where(PlaybookMetrics.playbook_name == playbook_name)
        )
        return list(result.scalars().all())
