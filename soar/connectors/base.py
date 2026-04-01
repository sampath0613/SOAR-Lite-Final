"""
Base connector interface and result model.
All connectors inherit from BaseConnector.
"""

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from pydantic import BaseModel


class ConnectorResult(BaseModel):
    """Standardized result returned by all connectors."""

    success: bool = True
    data: dict[str, Any] = None
    error: str | None = None
    raw_response: dict[str, Any] | None = None

    def __init__(self, **data):
        """Allow flexible initialization."""
        if data.get("data") is None:
            data["data"] = {}
        super().__init__(**data)


class BaseConnector(ABC):
    """Abstract base class for all connectors."""

    name: ClassVar[str]

    @abstractmethod
    async def execute(self, params: dict[str, Any]) -> ConnectorResult:
        """
        Execute connector action and return structured result.

        Args:
            params: Input parameters (e.g., {"ip": "8.8.8.8"})

        Returns:
            ConnectorResult with success status and data
        """
        ...

    async def health_check(self) -> bool:
        """
        Check if connector is healthy/reachable.
        Override in subclasses if supported.

        Returns:
            True if healthy, False otherwise
        """
        return True
