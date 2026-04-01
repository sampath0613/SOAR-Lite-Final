"""Health check endpoint."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status

from soar.connectors.registry import health_check_all

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=dict[str, Any])
async def health_check() -> dict[str, Any]:
    """
    Health check endpoint.

    Returns:
        Service status and connector health
    """
    try:
        # Check all connectors
        connector_health = await health_check_all()

        # Determine overall status
        all_healthy = all(connector_health.values())
        overall_status = "ok" if all_healthy else "degraded"

        return {
            "status": overall_status,
            "connectors": connector_health,
        }

    except Exception as error:
        logger.error(f"Health check error: {error}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Health check failed",
        )
