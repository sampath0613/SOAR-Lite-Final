"""Unit tests for connector registry behavior."""

import pytest

from soar.connectors.base import BaseConnector, ConnectorResult
from soar.connectors import registry


class HealthyConnector(BaseConnector):
    """Test connector that reports healthy."""

    name = "healthy"

    async def execute(self, params):
        return ConnectorResult(success=True, data={"ok": True})

    async def health_check(self) -> bool:
        return True


class UnhealthyConnector(BaseConnector):
    """Test connector that fails health checks."""

    name = "unhealthy"

    async def execute(self, params):
        return ConnectorResult(success=False, error="bad")

    async def health_check(self) -> bool:
        raise RuntimeError("health failed")


@pytest.mark.asyncio
async def test_init_list_get_connector():
    """Registry should initialize and resolve named connectors."""
    registry.init_connectors()

    names = set(registry.list_connectors())
    assert {"virustotal", "abuseipdb", "shodan", "slack", "mock_jira"}.issubset(names)

    connector = registry.get_connector("mock_jira")
    assert connector.name == "mock_jira"


def test_get_connector_missing_raises():
    """Unknown connector lookup should raise KeyError with available names."""
    registry.CONNECTOR_REGISTRY = {"healthy": HealthyConnector()}

    with pytest.raises(KeyError) as error:
        registry.get_connector("missing")

    assert "Available" in str(error.value)


@pytest.mark.asyncio
async def test_health_check_all_handles_exceptions():
    """health_check_all should return False when a connector health check crashes."""
    original = dict(registry.CONNECTOR_REGISTRY)
    registry.CONNECTOR_REGISTRY = {
        "healthy": HealthyConnector(),
        "broken": UnhealthyConnector(),
    }

    try:
        results = await registry.health_check_all()
    finally:
        registry.CONNECTOR_REGISTRY = original

    assert results["healthy"] is True
    assert results["broken"] is False
