"""Analytics and summary statistics endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from soar.db.database import get_db
from soar.models.incident import Incident, StepExecution, IncidentStatus, StepStatus

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/summary", response_model=dict[str, Any])
async def get_summary(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Get analytics summary for all incidents.

    Returns:
        Total incidents, breakdown by status, resolution times, error rates
    """
    try:
        # Total incidents
        total_result = await db.execute(select(func.count(Incident.id)))
        total_incidents = total_result.scalar() or 0

        # By status breakdown
        status_breakdown = {}
        for status_val in IncidentStatus:
            result = await db.execute(
                select(func.count(Incident.id)).where(Incident.status == status_val)
            )
            status_breakdown[status_val.value] = result.scalar() or 0

        # Average resolution time for completed incidents
        completed_result = await db.execute(
            select(Incident).where(
                Incident.status == IncidentStatus.COMPLETED,
                Incident.resolved_at.is_not(None),
            )
        )
        completed_incidents = completed_result.unique().scalars().all()

        avg_resolution_seconds = 0
        if completed_incidents:
            total_seconds = 0
            for inc in completed_incidents:
                if inc.resolved_at and inc.created_at:
                    duration = (inc.resolved_at - inc.created_at).total_seconds()
                    total_seconds += duration
            avg_resolution_seconds = int(total_seconds / len(completed_incidents))

        # False positive rate
        verdicted_result = await db.execute(
            select(func.count(Incident.id)).where(
                Incident.analyst_verdict.is_not(None),
            )
        )
        total_verdicted = verdicted_result.scalar() or 0

        false_positive_result = await db.execute(
            select(func.count(Incident.id)).where(
                Incident.analyst_verdict == "false_positive",
            )
        )
        false_positive_count = false_positive_result.scalar() or 0

        false_positive_rate = (
            round(false_positive_count / total_verdicted, 2)
            if total_verdicted > 0
            else 0
        )

        # Connector error rates
        connector_stats = {}

        # Group by connector
        from sqlalchemy import distinct
        connectors_result = await db.execute(
            select(distinct(StepExecution.connector_name))
        )
        connectors = [c[0] for c in connectors_result]

        for connector_name in connectors:
            failed_result = await db.execute(
                select(func.count(StepExecution.id)).where(
                    (StepExecution.connector_name == connector_name) &
                    (StepExecution.status == StepStatus.FAILED)
                )
            )
            failed_count = failed_result.scalar() or 0

            executed_result = await db.execute(
                select(func.count(StepExecution.id)).where(
                    StepExecution.connector_name == connector_name
                )
            )
            executed_count = executed_result.scalar() or 1

            error_rate = round(failed_count / executed_count, 2)
            connector_stats[connector_name] = {
                "total_executions": executed_count,
                "failed": failed_count,
                "error_rate": error_rate,
            }

        return {
            "total_incidents": total_incidents,
            "by_status": status_breakdown,
            "avg_resolution_time_seconds": avg_resolution_seconds,
            "false_positive_rate": false_positive_rate,
            "connector_error_rates": connector_stats,
        }

    except Exception as error:
        logger.error(f"Summary error: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compute summary",
        )
