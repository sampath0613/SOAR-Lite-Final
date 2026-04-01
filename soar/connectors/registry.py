"""
Connector registry for dynamic connector resolution.
Populated at startup, accessed by executor at runtime.
"""

import logging
from typing import Dict

from soar.connectors.base import BaseConnector

logger = logging.getLogger(__name__)

# Module-level registry populated at startup
CONNECTOR_REGISTRY: Dict[str, BaseConnector] = {}


def init_connectors() -> None:
    """
    Initialize all connectors and populate registry.
    Called from main.py on FastAPI startup.
    """
    global CONNECTOR_REGISTRY

    # Import MVP connectors only
    from soar.connectors.virustotal import VirusTotalConnector
    from soar.connectors.abuseipdb import AbuseIPDBConnector
    from soar.connectors.mock_jira import MockJiraConnector

    # Instantiate and register
    CONNECTOR_REGISTRY = {
        "virustotal": VirusTotalConnector(),
        "abuseipdb": AbuseIPDBConnector(),
        "mock_jira": MockJiraConnector(),
    }

    logger.info(
        "Initialized %s connectors: %s",
        len(CONNECTOR_REGISTRY),
        list(CONNECTOR_REGISTRY.keys()),
    )


def get_connector(name: str) -> BaseConnector:
    """
    Resolve connector by name from registry.

    Args:
        name: Connector name

    Returns:
        BaseConnector instance

    Raises:
        KeyError: If connector not found
    """
    if name not in CONNECTOR_REGISTRY:
        available = ", ".join(CONNECTOR_REGISTRY.keys())
        raise KeyError(f"Connector '{name}' not found. Available: {available}")

    return CONNECTOR_REGISTRY[name]


def list_connectors() -> list[str]:
    """Get list of all registered connector names."""
    return list(CONNECTOR_REGISTRY.keys())


async def health_check_all() -> dict[str, bool]:
    """Check health of all connectors."""
    results = {}
    for name, connector in CONNECTOR_REGISTRY.items():
        try:
            results[name] = await connector.health_check()
        except Exception as error:
            logger.warning(f"Health check failed for {name}: {error}")
            results[name] = False

    return results
