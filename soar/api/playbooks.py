"""Playbook information and analytics endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from soar.db.database import get_db
from soar.main import APP_STATE

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=dict[str, Any])
async def list_playbooks() -> dict[str, Any]:
    """
    List all loaded playbooks with metadata.

    Returns:
        List of playbooks with name, trigger conditions, and step count
    """
    try:
        playbooks = APP_STATE.get("playbooks", {})

        if not playbooks:
            return {
                "playbooks": [],
                "count": 0,
            }

        playbook_list = []
        for name, playbook in playbooks.items():
            playbook_list.append({
                "name": playbook.name,
                "trigger_alert_type": playbook.trigger_alert_type,
                "min_severity": playbook.min_severity,
                "step_count": len(playbook.steps),
                "steps": [
                    {
                        "id": step.id,
                        "connector": step.connector,
                        "input_field": step.input_field,
                    }
                    for step in playbook.steps
                ],
            })

        return {
            "playbooks": playbook_list,
            "count": len(playbook_list),
        }

    except Exception as error:
        logger.error(f"List playbooks error: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list playbooks",
        )


@router.get("/{playbook_name}/step-utility", response_model=dict[str, Any])
async def get_step_utility(
    playbook_name: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Get per-step utility scores for a playbook.

    Utility score = (true_positive executions) / (total vetted executions)
    Recommendation: >= 0.4 = "keep", < 0.4 = "review"

    Returns:
        Playbook with steps and their utility scores
    """
    try:
        from soar.analytics.utility import compute_step_utility

        playbooks = APP_STATE.get("playbooks", {})
        playbook = playbooks.get(playbook_name)

        if not playbook:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Playbook {playbook_name} not found",
            )

        # Compute utility for each step
        steps_with_utility = []
        for step in playbook.steps:
            try:
                utility_score = await compute_step_utility(playbook_name, step.id, db)
            except Exception as error:
                logger.warning(f"Failed to compute utility for step {step.id}: {error}")
                utility_score = 0.5  # Default neutral

            # Determine recommendation
            recommendation = "keep" if utility_score >= 0.4 else "review"

            # Get metrics from DB
            from soar.db.crud import get_playbook_metrics
            metrics = await get_playbook_metrics(db, playbook_name, step.id)

            steps_with_utility.append({
                "step_id": step.id,
                "connector": step.connector,
                "utility_score": round(utility_score, 2),
                "recommendation": recommendation,
                "executions": metrics.execution_count if metrics else 0,
            })

        return {
            "playbook": playbook_name,
            "trigger_alert_type": playbook.trigger_alert_type,
            "min_severity": playbook.min_severity,
            "steps": steps_with_utility,
        }

    except HTTPException:
        raise

    except Exception as error:
        logger.error(f"Get step utility error: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compute step utility",
        )
