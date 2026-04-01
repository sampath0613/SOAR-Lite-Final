"""
SQLAlchemy ORM models using Mapped[] syntax (SQLAlchemy 2.x).
Three tables: incidents, step_executions, playbook_metrics
"""

from datetime import datetime, timezone
from enum import Enum as PyEnum
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    String,
    Integer,
    DateTime,
    Enum,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class IncidentStatus(PyEnum):
    """Incident execution status enum."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ESCALATED = "escalated"


class StepStatus(PyEnum):
    """Step execution status enum."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Incident(Base):
    """
    Represents the execution of a playbook in response to an alert.
    Tracks incident metadata, final status, and analyst verdict.
    """

    __tablename__ = "incidents"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # Foreign key to alert
    alert_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # Playbook name that was executed
    playbook_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Incident status tracking
    status: Mapped[str] = mapped_column(
        Enum(IncidentStatus),
        default=IncidentStatus.PENDING,
        nullable=False,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Analyst verdict after incident is completed
    analyst_verdict: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="true_positive or false_positive",
    )

    # Raw alert JSON for reference
    raw_alert_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Stringified JSON of the original alert",
    )

    # Relationship to step executions
    step_executions: Mapped[list["StepExecution"]] = relationship(
        "StepExecution",
        back_populates="incident",
        cascade="all, delete-orphan",
        lazy="joined",
    )

    def __repr__(self) -> str:
        return f"<Incident {self.id} status={self.status} playbook={self.playbook_name}>"


class StepExecution(Base):
    """
    Tracks execution of a single playbook step.
    Records connector invocation, input/output, and retry attempts.
    """

    __tablename__ = "step_executions"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # Foreign key to incident
    incident_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Step identifier from playbook
    step_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # Connector name that executed this step
    connector_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Execution status
    status: Mapped[str] = mapped_column(
        Enum(StepStatus),
        default=StepStatus.PENDING,
        nullable=False,
    )

    # Input parameters as JSON string
    input_params_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Stringified JSON of input parameters",
    )

    # Result output as JSON string (nullable until execution completes)
    result_json: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Stringified JSON of ConnectorResult data",
    )

    # Timestamps
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Retry tracking
    attempt_number: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    # Relationship back to incident
    incident: Mapped[Incident] = relationship(
        "Incident",
        back_populates="step_executions",
    )

    def __repr__(self) -> str:
        return (
            f"<StepExecution {self.id} step={self.step_id} "
            f"status={self.status} attempt={self.attempt_number}>"
        )


class PlaybookMetrics(Base):
    """
    Aggregates per-step utility scores across all incident verdicts.
    Used to identify low-signal steps for playbook optimization.
    """

    __tablename__ = "playbook_metrics"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # Composite: playbook_name + step_id identifies the metric
    playbook_name: Mapped[str] = mapped_column(String(255), nullable=False)

    step_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # Execution counts
    execution_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Total number of times this step executed",
    )

    verdict_changed_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of executions where verdict changed",
    )

    # Last computation timestamp
    last_computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<PlaybookMetrics {self.playbook_name}/{self.step_id} "
            f"executions={self.execution_count}>"
        )
