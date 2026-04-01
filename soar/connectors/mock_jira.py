"""Mock JIRA connector for local ticket simulation (no external HTTP)."""

import logging
from random import randint
from typing import Any, ClassVar

from soar.connectors.base import BaseConnector, ConnectorResult

logger = logging.getLogger(__name__)


class MockJiraConnector(BaseConnector):
    """
    Mock JIRA connector for testing and offline scenarios.
    No external HTTP calls - simulates ticket creation entirely locally.
    """

    name: ClassVar[str] = "mock_jira"

    async def execute(self, params: dict[str, Any]) -> ConnectorResult:
        """
        Simulate JIRA ticket creation.

        Args:
            params: Can contain:
                - "alert_id": alert ID
                - "title": ticket title
                - "description": ticket description
                - "priority": ticket priority (optional)

        Returns:
            ConnectorResult with fake ticket ID (SOAR-XXXX format)
        """
        alert_id = params.get("alert_id", "unknown")
        title = params.get("title", f"SOAR Alert: {alert_id}")
        priority = params.get("priority", "Medium")

        # Generate fake ticket ID
        ticket_number = randint(1000, 9999)
        ticket_id = f"SOAR-{ticket_number}"

        # Log ticket creation
        logger.info(
            f"MockJira: Created ticket {ticket_id} for alert {alert_id} "
            f"with priority {priority}"
        )

        result_data = {
            "ticket_id": ticket_id,
            "alert_id": alert_id,
            "title": title,
            "status": "created",
            "priority": priority,
        }

        return ConnectorResult(
            success=True,
            data=result_data,
            raw_response=None,
        )

    async def health_check(self) -> bool:
        """Mock JIRA is always healthy (no external dependency)."""
        logger.debug("MockJira health check: OK")
        return True
