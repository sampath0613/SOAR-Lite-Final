"""Dashboard pages for incident queue and incident detail views."""

import json
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from soar.db.crud import (
    get_incident,
    get_step_executions_for_incident,
    list_incidents,
    update_incident_verdict,
)
from soar.db.database import get_db

router = APIRouter()

_templates_dir = Path(__file__).resolve().parent.parent.parent / "dashboard" / "templates"
templates = Jinja2Templates(directory=str(_templates_dir))


def _incident_status_value(value: object) -> str:
    """Normalize status values for template rendering."""
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Render incident queue page with status badges and auto-refresh."""
    incidents, _ = await list_incidents(db=db, page=1, page_size=100)

    items = []
    for incident in incidents:
        try:
            raw_alert = json.loads(incident.raw_alert_json)
        except json.JSONDecodeError:
            raw_alert = {}

        items.append(
            {
                "id": incident.id,
                "alert_type": raw_alert.get("alert_type", "unknown"),
                "severity": raw_alert.get("severity", "unknown"),
                "playbook_name": incident.playbook_name,
                "status": _incident_status_value(incident.status),
                "created_at": incident.created_at.isoformat() if incident.created_at else "",
            }
        )

    return templates.TemplateResponse(
        request=request,
        name="incidents.html",
        context={
            "title": "SOAR-Lite Dashboard",
            "incidents": items,
        },
    )


@router.get("/dashboard/incidents/{incident_id}", response_class=HTMLResponse)
async def dashboard_incident_detail(
    incident_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Render incident detail page with timeline and verdict action form."""
    incident = await get_incident(db, incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} not found",
        )

    try:
        alert_payload = json.loads(incident.raw_alert_json)
    except json.JSONDecodeError:
        alert_payload = {}

    steps = []
    for step in await get_step_executions_for_incident(db, incident_id):
        duration_seconds = None
        if step.started_at and step.completed_at:
            duration_seconds = (step.completed_at - step.started_at).total_seconds()

        try:
            result_data = json.loads(step.result_json) if step.result_json else {}
        except json.JSONDecodeError:
            result_data = {}

        steps.append(
            {
                "step_id": step.step_id,
                "connector": step.connector_name,
                "status": _incident_status_value(step.status),
                "duration_seconds": duration_seconds,
                "result_summary": result_data,
                "started_at": step.started_at.isoformat() if step.started_at else "",
                "completed_at": step.completed_at.isoformat() if step.completed_at else "",
            }
        )

    return templates.TemplateResponse(
        request=request,
        name="incident_detail.html",
        context={
            "title": f"Incident {incident.id}",
            "incident": {
                "id": incident.id,
                "playbook_name": incident.playbook_name,
                "status": _incident_status_value(incident.status),
                "created_at": incident.created_at.isoformat() if incident.created_at else "",
                "resolved_at": incident.resolved_at.isoformat() if incident.resolved_at else "",
                "analyst_verdict": incident.analyst_verdict,
            },
            "alert": alert_payload,
            "steps": steps,
        },
    )


@router.post("/dashboard/incidents/{incident_id}/verdict")
async def dashboard_set_verdict(
    incident_id: str,
    verdict: str = Form(...),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Persist analyst verdict from dashboard and redirect back to detail page."""
    await update_incident_verdict(db, incident_id, verdict)

    return RedirectResponse(
        url=f"/dashboard/incidents/{incident_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
