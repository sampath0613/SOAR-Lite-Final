"""Incident query and management endpoints."""

import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from soar.db.crud import (
    get_incident,
    list_incidents,
    update_incident_verdict,
    get_step_executions_for_incident,
)
from soar.db.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=dict[str, Any])
async def list_incidents_endpoint(
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    List incidents with optional filtering and pagination.

    Query parameters:
    - status: Filter by status (pending|running|completed|failed|escalated)
    - page: Page number (1-indexed)
    - page_size: Items per page (max 100)

    Returns:
        Paginated list of incidents
    """
    try:
        incidents, total_count = await list_incidents(
            db=db,
            status=status_filter,
            page=page,
            page_size=page_size,
        )

        # Extract summary fields
        incident_summaries = []
        for incident in incidents:
            try:
                raw_alert = json.loads(incident.raw_alert_json)
                severity = raw_alert.get("severity", "unknown")
            except json.JSONDecodeError:
                severity = "unknown"

            incident_summaries.append({
                "id": incident.id,
                "alert_id": incident.alert_id,
                "playbook_name": incident.playbook_name,
                "status": incident.status,
                "severity": severity,
                "created_at": incident.created_at.isoformat() if incident.created_at else None,
                "resolved_at": incident.resolved_at.isoformat() if incident.resolved_at else None,
                "analyst_verdict": incident.analyst_verdict,
            })

        return {
            "incidents": incident_summaries,
            "total": total_count,
            "page": page,
            "page_size": page_size,
        }

    except Exception as error:
        logger.error(f"List incidents error: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list incidents",
        )


@router.get("/{incident_id}", response_model=dict[str, Any])
async def get_incident_detail(
    incident_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Get incident detail with step execution timeline.

    Returns:
        Full incident with nested step_executions
    """
    try:
        incident = await get_incident(db, incident_id)
        if not incident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incident {incident_id} not found",
            )

        # Get step executions
        step_executions = await get_step_executions_for_incident(db, incident_id)

        # Parse alert JSON
        try:
            raw_alert = json.loads(incident.raw_alert_json)
        except json.JSONDecodeError:
            raw_alert = {}

        # Format step execution timeline
        steps_timeline = []
        for step_exec in step_executions:
            duration_seconds = None
            if step_exec.completed_at and step_exec.started_at:
                duration_seconds = (step_exec.completed_at - step_exec.started_at).total_seconds()

            try:
                result_data = json.loads(step_exec.result_json) if step_exec.result_json else {}
            except json.JSONDecodeError:
                result_data = {}

            steps_timeline.append({
                "id": step_exec.id,
                "step_id": step_exec.step_id,
                "connector": step_exec.connector_name,
                "status": step_exec.status,
                "input": (
                    json.loads(step_exec.input_params_json)
                    if step_exec.input_params_json
                    else {}
                ),
                "result": result_data,
                "duration_seconds": duration_seconds,
                "attempt_number": step_exec.attempt_number,
                "started_at": step_exec.started_at.isoformat() if step_exec.started_at else None,
                "completed_at": (
                    step_exec.completed_at.isoformat()
                    if step_exec.completed_at
                    else None
                ),
            })

        return {
            "id": incident.id,
            "alert_id": incident.alert_id,
            "playbook_name": incident.playbook_name,
            "status": incident.status,
            "analyst_verdict": incident.analyst_verdict,
            "created_at": incident.created_at.isoformat() if incident.created_at else None,
            "resolved_at": incident.resolved_at.isoformat() if incident.resolved_at else None,
            "alert": raw_alert,
            "steps": steps_timeline,
        }

    except HTTPException:
        raise

    except Exception as error:
        logger.error(f"Get incident detail error: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get incident detail",
        )


@router.patch("/{incident_id}/verdict", response_model=dict[str, Any])
async def update_verdict(
    incident_id: str,
    verdict_data: dict[str, str],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Update analyst verdict for an incident.

    Request body:
    - verdict: "true_positive" or "false_positive"

    Returns:
        Updated incident
    """
    try:
        verdict = verdict_data.get("verdict", "").lower()

        if verdict not in ["true_positive", "false_positive"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="verdict must be 'true_positive' or 'false_positive'",
            )

        incident = await update_incident_verdict(db, incident_id, verdict)

        logger.info(f"Updated incident {incident_id} verdict to {verdict}")

        # Trigger utility score recomputation (async)
        # TODO: queue async task for analytics.recompute_playbook_metrics()

        return {
            "id": incident.id,
            "analyst_verdict": incident.analyst_verdict,
            "status": incident.status,
        }

    except HTTPException:
        raise

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )

    except Exception as error:
        logger.error(f"Update verdict error: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update verdict",
        )
