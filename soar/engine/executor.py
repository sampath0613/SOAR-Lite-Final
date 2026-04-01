"""
Playbook execution engine.
Core orchestration logic: executes steps sequentially with retry logic.
"""

import asyncio
import json
import logging
from typing import Any

from simpleeval import EvalWithCompoundTypes, FeatureNotAvailable
from sqlalchemy.ext.asyncio import AsyncSession

from soar.connectors.registry import get_connector
from soar.db.crud import (
    create_step_execution,
    update_step_execution,
    update_incident_status,
    get_incident,
)
from soar.engine.state_machine import validate_incident_transition
from soar.models.alert import Alert
from soar.models.incident import IncidentStatus, StepStatus
from soar.models.playbook import Playbook

logger = logging.getLogger(__name__)


async def execute_playbook(
    incident_id: str,
    playbook: Playbook,
    alert: Alert,
    db: AsyncSession,
) -> None:
    """
    Execute a playbook for an incident.

    Orchestration logic:
    1. Update incident status to RUNNING
    2. For each step:
       a. Create step_execution record
       b. Resolve connector from registry
       c. Execute with retry logic (exponential backoff)
       d. Evaluate on_result conditions
       e. Route: escalate, continue, or close
    3. On completion or error: update incident status

    Args:
        incident_id: The incident UUID
        playbook: Playbook to execute
        alert: Alert that triggered the playbook
        db: AsyncSession for database operations

    Raises:
        All exceptions are caught and incident marked FAILED
    """
    try:
        # Get incident from DB
        incident = await get_incident(db, incident_id)
        if not incident:
            logger.error(f"Incident {incident_id} not found")
            return

        # Validate state transition
        incident_state = (
            incident.status.value
            if hasattr(incident.status, "value")
            else str(incident.status).lower()
        )
        validate_incident_transition(incident_state, IncidentStatus.RUNNING.value)

        # Update incident status to RUNNING
        await update_incident_status(db, incident_id, IncidentStatus.RUNNING.value)
        logger.info(f"[{incident_id}] Starting playbook execution: {playbook.name}")

        # Execute each step
        for step in playbook.steps:
            try:
                # Attempt step execution with retries
                await _execute_step(
                    incident_id=incident_id,
                    step=step,
                    alert=alert,
                    db=db,
                    playbook_name=playbook.name,
                )

                # Check if we should stop (escalate/close)
                incident = await get_incident(db, incident_id)
                current_status = (
                    incident.status.value
                    if hasattr(incident.status, "value")
                    else str(incident.status).lower()
                )
                if current_status in [
                    IncidentStatus.ESCALATED.value,
                    IncidentStatus.COMPLETED.value,
                ]:
                    logger.info(f"[{incident_id}] Playbook stopped: {incident.status}")
                    return

            except Exception as step_error:
                logger.error(
                    f"[{incident_id}] Step {step.id} failed critically: {step_error}"
                )
                await update_incident_status(db, incident_id, IncidentStatus.FAILED.value)
                return

        # All steps completed successfully
        await update_incident_status(db, incident_id, IncidentStatus.COMPLETED.value)
        logger.info(f"[{incident_id}] Playbook completed successfully")

    except Exception as error:
        logger.error(f"[{incident_id}] Playbook execution failed: {error}")
        try:
            await update_incident_status(db, incident_id, IncidentStatus.FAILED.value)
        except Exception as update_error:
            logger.error(f"Failed to mark incident FAILED: {update_error}")


async def _execute_step(
    incident_id: str,
    step: Any,  # Step model
    alert: Alert,
    db: AsyncSession,
    playbook_name: str,
) -> None:
    """
    Execute a single step with retry logic and condition evaluation.

    Args:
        incident_id: Parent incident UUID
        step: Step from playbook
        alert: Alert instance
        db: AsyncSession
        playbook_name: Name of playbook

    Raises:
        Exception if step fails critically after all retries
    """
    # Extract input value from alert
    if not hasattr(alert, step.input_field):
        logger.error(
            f"[{incident_id}] Step {step.id}: alert missing field {step.input_field}"
        )
        await update_incident_status(db, incident_id, IncidentStatus.ESCALATED.value)
        raise ValueError(f"Alert missing field: {step.input_field}")

    input_value = getattr(alert, step.input_field)
    params = {step.input_field: input_value}

    # Create step execution record
    step_exec = await create_step_execution(
        db=db,
        incident_id=incident_id,
        step_id=step.id,
        connector_name=step.connector,
        input_params_json=json.dumps(params),
    )

    logger.info(
        f"[{incident_id}] Starting step {step.id} via {step.connector} "
        f"(input: {step.input_field}={input_value})"
    )

    # Get connector from registry
    try:
        connector = get_connector(step.connector)
    except KeyError as error:
        logger.error(f"[{incident_id}] Step {step.id}: {error}")
        await update_incident_status(db, incident_id, IncidentStatus.ESCALATED.value)
        raise

    # Execute with retry loop
    result = None
    last_error = None

    for attempt in range(1, step.retries + 1):
        try:
            # Update step status to RUNNING
            await update_step_execution(
                db=db,
                step_execution_id=step_exec.id,
                status=StepStatus.RUNNING.value,
                attempt_number=attempt,
            )

            # Execute connector with timeout
            result = await asyncio.wait_for(
                connector.execute(params),
                timeout=step.timeout,
            )

            # Update step as completed
            await update_step_execution(
                db=db,
                step_execution_id=step_exec.id,
                status=StepStatus.COMPLETED.value,
                result_json=json.dumps(
                    result.model_dump() if hasattr(result, "model_dump") else result.data
                ),
                completed_at=None,
            )

            logger.info(
                f"[{incident_id}] Step {step.id} completed on attempt {attempt}"
            )
            break

        except asyncio.TimeoutError:
            last_error = f"Timeout after {step.timeout}s"
            logger.warning(
                f"[{incident_id}] Step {step.id} attempt {attempt}: {last_error}"
            )

            if attempt < step.retries:
                wait_time = 2 ** attempt  # Exponential backoff
                logger.debug(f"[{incident_id}] Waiting {wait_time}s before retry...")
                await asyncio.sleep(wait_time)

        except Exception as error:
            last_error = str(error)
            logger.warning(
                f"[{incident_id}] Step {step.id} attempt {attempt}: {last_error}"
            )

            if attempt < step.retries:
                wait_time = 2 ** attempt  # Exponential backoff
                logger.debug(f"[{incident_id}] Waiting {wait_time}s before retry...")
                await asyncio.sleep(wait_time)

    # After retries exhausted
    if result is None:
        logger.error(
            f"[{incident_id}] Step {step.id} failed after {step.retries} attempts: {last_error}"
        )
        await update_step_execution(
            db=db,
            step_execution_id=step_exec.id,
            status=StepStatus.FAILED.value,
        )
        await update_incident_status(db, incident_id, IncidentStatus.ESCALATED.value)
        raise RuntimeError(f"Step {step.id} failed after {step.retries} retries: {last_error}")

    # Evaluate on_result conditions
    await _evaluate_conditions(
        incident_id=incident_id,
        step_id=step.id,
        conditions=step.on_result,
        result_data=result.data,
        db=db,
    )


async def _evaluate_conditions(
    incident_id: str,
    step_id: str,
    conditions: list[Any],  # Condition models
    result_data: dict[str, Any],
    db: AsyncSession,
) -> None:
    """
    Evaluate on_result conditions and route incident.

    Args:
        incident_id: Parent incident UUID
        step_id: Current step ID
        conditions: List of Condition models
        result_data: Result data from connector
        db: AsyncSession
    """
    for condition in conditions:
        # Evaluate if expression
        if condition.if_expr is None:
            # No condition = else (fallback)
            should_execute = True
        else:
            try:
                # Safe evaluation with simpleeval
                should_execute = EvalWithCompoundTypes(
                    names=result_data,
                    functions={},
                ).eval(condition.if_expr)
            except (FeatureNotAvailable, Exception) as error:
                logger.warning(
                    f"[{incident_id}] Condition evaluation failed: {error}. Treating as False."
                )
                should_execute = False

        if should_execute:
            logger.info(
                f"[{incident_id}] Step {step_id}: condition "
                f"'{condition.if_expr}' -> {condition.then}"
            )

            if condition.then == "escalate":
                await update_incident_status(db, incident_id, IncidentStatus.ESCALATED.value)
                return

            elif condition.then == "close":
                await update_incident_status(db, incident_id, IncidentStatus.COMPLETED.value)
                return

            elif condition.then == "continue":
                # Continue to next step
                return

            # else: condition.then is a step_id (not implemented in MVP)

    # If no condition matched and no condition was executed, log warning
    logger.warning(f"[{incident_id}] Step {step_id}: no matching condition found")
