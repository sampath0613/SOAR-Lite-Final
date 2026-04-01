"""
Alert to playbook matching engine.
Matches incoming alerts to playbooks based on type and severity.
"""

import logging
from typing import Dict, Optional

from soar.models.alert import Alert
from soar.models.playbook import Playbook

logger = logging.getLogger(__name__)

# Severity hierarchy for comparison
SEVERITY_ORDER = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


async def match_playbook(
    alert: Alert,
    playbooks: Dict[str, Playbook],
) -> Optional[Playbook]:
    """
    Find a playbook matching the alert's type and severity.

    Matching logic:
    - Find first playbook where alert.alert_type == playbook.trigger_alert_type
    - AND alert.severity >= playbook.min_severity

    Args:
        alert: Incoming alert to match
        playbooks: Dict of available playbooks keyed by name

    Returns:
        Matching Playbook or None if no match found
    """
    alert_severity_level = SEVERITY_ORDER.get(alert.severity, 0)

    for playbook in playbooks.values():
        playbook_severity_level = SEVERITY_ORDER.get(playbook.min_severity, 0)

        # Check type match
        if alert.alert_type.lower() == playbook.trigger_alert_type.lower():
            # Check severity meets minimum
            if alert_severity_level >= playbook_severity_level:
                logger.info(
                    f"Alert {alert.alert_id} matched to playbook '{playbook.name}' "
                    f"(type={alert.alert_type}, severity={alert.severity})"
                )
                return playbook

    # No match found
    logger.warning(
        f"No playbook matched for alert {alert.alert_id} "
        f"(type={alert.alert_type}, severity={alert.severity})"
    )
    return None


async def find_playbook_by_name(
    playbook_name: str,
    playbooks: Dict[str, Playbook],
) -> Optional[Playbook]:
    """
    Find a playbook by its name.

    Args:
        playbook_name: Name of playbook to find
        playbooks: Dict of available playbooks

    Returns:
        Playbook or None if not found
    """
    return playbooks.get(playbook_name)
