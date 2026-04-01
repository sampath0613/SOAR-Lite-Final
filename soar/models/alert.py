"""
Pydantic models for security alerts with adaptive normalization.
Supports multiple alert sources: Splunk, QRadar, mock.
"""

from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class Alert(BaseModel):
    """
    Normalized security alert model.
    All alert sources are normalized to this schema.
    """

    alert_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique alert ID")
    alert_type: str = Field(..., description="Alert type (e.g., phishing, malware, bruteforce)")
    severity: Literal["low", "medium", "high", "critical"] = Field(
        ..., description="Alert severity level"
    )
    source_ip: str = Field(..., description="Source IP address")
    destination_ip: str | None = Field(
        default=None, description="Destination IP address (optional)"
    )
    timestamp: datetime = Field(default_factory=datetime.now, description="Alert timestamp")
    raw_payload: dict[str, Any] = Field(
        default_factory=dict, description="Original alert payload from source system"
    )
    source_system: Literal["splunk", "qradar", "mock"] = Field(
        ..., description="System that generated the alert"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "alert_id": "abc-123-def",
                "alert_type": "phishing",
                "severity": "high",
                "source_ip": "192.168.1.100",
                "destination_ip": "10.0.0.1",
                "timestamp": "2026-04-01T13:42:48Z",
                "raw_payload": {"email": "attacker@evil.com"},
                "source_system": "splunk",
            }
        }
    )


def normalize_splunk(raw: dict[str, Any]) -> Alert:
    """
    Normalize Splunk alert JSON to standard Alert model.

    Expected Splunk fields:
    - alert_type: string
    - severity: low|medium|high|critical
    - source_ip: string
    - dest_ip: optional string
    - timestamp: ISO string or epoch
    - event: raw event data
    """
    try:
        return Alert(
            alert_type=raw.get("alert_type", "unknown"),
            severity=raw.get("severity", "medium").lower(),
            source_ip=raw.get("source_ip") or raw.get("src_ip", "0.0.0.0"),
            destination_ip=raw.get("dest_ip") or raw.get("destination_ip"),
            timestamp=raw.get("timestamp", datetime.now()),
            raw_payload=raw,
            source_system="splunk",
        )
    except Exception as e:
        raise ValueError(f"Failed to normalize Splunk alert: {e}")


def normalize_qradar(raw: dict[str, Any]) -> Alert:
    """
    Normalize QRadar alert JSON to standard Alert model.

    Expected QRadar fields:
    - alert_type: string
    - severity: low|medium|high|critical
    - source_ip: string
    - destination_ip: optional string
    - timestamp: ISO string or epoch
    - event_payload: raw event data
    """
    try:
        return Alert(
            alert_type=raw.get("alert_type", "unknown"),
            severity=raw.get("severity", "medium").lower(),
            source_ip=raw.get("source_ip") or raw.get("src_ip", "0.0.0.0"),
            destination_ip=raw.get("destination_ip") or raw.get("dest_ip"),
            timestamp=raw.get("timestamp", datetime.now()),
            raw_payload=raw,
            source_system="qradar",
        )
    except Exception as e:
        raise ValueError(f"Failed to normalize QRadar alert: {e}")


def normalize_mock(raw: dict[str, Any]) -> Alert:
    """
    Normalize mock alert JSON (mostly pass-through for testing).
    """
    try:
        return Alert(
            alert_type=raw.get("alert_type", "mock_alert"),
            severity=raw.get("severity", "medium").lower(),
            source_ip=raw.get("source_ip", "127.0.0.1"),
            destination_ip=raw.get("destination_ip"),
            timestamp=raw.get("timestamp", datetime.now()),
            raw_payload=raw,
            source_system="mock",
        )
    except Exception as e:
        raise ValueError(f"Failed to normalize mock alert: {e}")


def normalize(raw: dict[str, Any], source_system: str) -> Alert:
    """
    Factory function to normalize alerts from multiple sources.

    Args:
        raw: Raw alert JSON
        source_system: "splunk", "qradar", or "mock"

    Returns:
        Normalized Alert

    Raises:
        ValueError: If source_system unknown or normalization fails
    """
    normalizers = {
        "splunk": normalize_splunk,
        "qradar": normalize_qradar,
        "mock": normalize_mock,
    }

    if source_system not in normalizers:
        raise ValueError(
            f"Unknown source_system: {source_system}. "
            f"Available: {', '.join(normalizers.keys())}"
        )

    return normalizers[source_system](raw)
