"""
Step utility scoring algorithm.
Computes per-step utility scores to identify low-signal playbook steps.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from soar.db.crud import (
    get_step_executions_for_playbook_step,
    get_incident,
    upsert_playbook_metrics,
)

logger = logging.getLogger(__name__)


async def compute_step_utility(
    playbook_name: str,
    step_id: str,
    db: AsyncSession,
) -> float:
    """
    Compute utility score for a step across all incidents.

    Utility = (step executions where incident verdict=true_positive)
              / (total executions with an analyst verdict)

    Score interpretation:
    - >= 0.4: "keep" (useful)
    - < 0.4: "review" (potentially remove)

    Args:
        playbook_name: Name of playbook
        step_id: Step ID within playbook
        db: AsyncSession

    Returns:
        Utility score (float 0.0-1.0), or 0.5 if insufficient data
    """
    try:
        # Get all step executions for this step
        step_executions = await get_step_executions_for_playbook_step(
            db=db,
            playbook_name=playbook_name,
            step_id=step_id,
        )

        if not step_executions:
            logger.debug(f"No executions found for {playbook_name}/{step_id}")
            return 0.5  # Neutral score for no data

        # Count verdicts and successes
        successful_true_positives = 0
        total_with_verdict = 0

        for step_exec in step_executions:
            # Get parent incident
            incident = await get_incident(db, step_exec.incident_id)
            if not incident:
                continue

            # Only count if incident has a verdict
            if incident.analyst_verdict is None:
                continue

            total_with_verdict += 1

            # Count if analyst marked incident as true_positive.
            if incident.analyst_verdict == "true_positive":
                successful_true_positives += 1

        # Calculate utility
        if total_with_verdict == 0:
            logger.debug(f"No verdicts for {playbook_name}/{step_id}, using neutral score")
            return 0.5

        utility_score = successful_true_positives / total_with_verdict
        logger.info(
            f"Computed utility for {playbook_name}/{step_id}: "
            f"{successful_true_positives}/{total_with_verdict} = {utility_score:.2f}"
        )

        # Update metrics table
        await upsert_playbook_metrics(
            db=db,
            playbook_name=playbook_name,
            step_id=step_id,
            execution_count=total_with_verdict,
            verdict_changed_count=successful_true_positives,
        )

        return utility_score

    except Exception as error:
        logger.error(f"Error computing utility for {playbook_name}/{step_id}: {error}")
        return 0.5  # Default to neutral on error


async def recompute_playbook_metrics(
    playbook_name: str,
    db: AsyncSession,
) -> dict[str, float]:
    """
    Recompute all metrics for a playbook.
    Call this after an incident verdict is updated.

    Args:
        playbook_name: Name of playbook
        db: AsyncSession

    Returns:
        Dict of step_id -> utility_score
    """
    try:
        from soar.main import APP_STATE

        playbooks = APP_STATE.get("playbooks", {})
        playbook = playbooks.get(playbook_name)

        if not playbook:
            logger.warning(f"Playbook {playbook_name} not found")
            return {}

        results = {}

        for step in playbook.steps:
            utility = await compute_step_utility(playbook_name, step.id, db)
            results[step.id] = utility

        logger.info(f"Recomputed metrics for {playbook_name}: {results}")
        return results

    except Exception as error:
        logger.error(f"Error recomputing metrics for {playbook_name}: {error}")
        return {}
