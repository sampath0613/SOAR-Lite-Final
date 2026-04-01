"""Alert ingestion endpoint."""

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from soar.db.database import get_db
from soar.db.crud import create_incident
from soar.engine.executor import execute_playbook
from soar.engine.matcher import match_playbook
from soar.main import APP_STATE
from soar.models.alert import normalize

logger = logging.getLogger(__name__)
router = APIRouter()


class AlertIngestRequest(dict):
    """Flexible request model to accept any alert JSON."""

    pass


@router.post("/", status_code=status.HTTP_202_ACCEPTED)
async def ingest_alert(
    alert_data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Ingest a security alert and trigger playbook execution.

    Request body must include:
    - source_system: "splunk" | "qradar" | "mock"
    - Plus source-specific fields (alert_type, severity, source_ip, etc.)

    Returns:
        202 Accepted with incident_id and playbook_matched
    """
    try:
        # Extract source system
        source_system = alert_data.get("source_system")
        if not source_system:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="source_system is required",
            )

        # Normalize alert
        alert = normalize(alert_data, source_system)
        logger.info(f"Normalized alert {alert.alert_id}: {alert.alert_type}/{alert.severity}")

        # Match playbook
        playbooks = APP_STATE.get("playbooks", {})
        if not playbooks:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No playbooks loaded",
            )

        matched_playbook = await match_playbook(alert, playbooks)
        if not matched_playbook:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No playbook matched for alert type={alert.alert_type}, "
                f"severity={alert.severity}",
            )

        # Create incident
        incident = await create_incident(
            db=db,
            alert_id=alert.alert_id,
            playbook_name=matched_playbook.name,
            raw_alert_json=alert.model_dump_json(),
        )

        # Fire background task using a separate session to avoid sharing a request session.
        session_factory = async_sessionmaker(
            bind=db.bind,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )

        async def run_playbook_task() -> None:
            async with session_factory() as task_db:
                await execute_playbook(
                    incident_id=incident.id,
                    playbook=matched_playbook,
                    alert=alert,
                    db=task_db,
                )

        task = asyncio.create_task(run_playbook_task())

        # Track task
        APP_STATE["engine_tasks"][incident.id] = {
            "task": task,
            "created_at": None,  # Could timestamp this
            "status": "pending",
        }

        logger.info(
            f"Alert ingested: incident_id={incident.id}, playbook={matched_playbook.name}"
        )

        return {
            "status": "accepted",
            "incident_id": incident.id,
            "playbook_matched": matched_playbook.name,
            "alert_id": alert.alert_id,
        }

    except HTTPException:
        raise

    except ValueError as error:
        logger.warning(f"Alert normalization error: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid alert: {str(error)}",
        )

    except Exception as error:
        logger.error(f"Alert ingestion error: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
