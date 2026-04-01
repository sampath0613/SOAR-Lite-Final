"""
Pydantic models for SOAR playbook definitions.
Playbooks are YAML files containing orchestration logic.
"""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Condition(BaseModel):
    """
    A conditional routing rule within a playbook step.
    Evaluates an expression and routes to an action.
    """

    if_expr: Optional[str] = Field(
        default=None,
        description="Expression to evaluate (e.g., 'score > 70'). If None, acts as 'else'.",
    )
    then: Literal["escalate", "continue", "close", "step_id"] | str = Field(
        ..., description="Action or next step: escalate, continue, close, or step ID"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "if_expr": "score > 70",
                "then": "escalate",
            }
        }
    )


class Step(BaseModel):
    """
    A single orchestration step that executes via a connector.
    """

    id: str = Field(..., description="Unique step identifier within playbook")
    connector: str = Field(..., description="Connector name (e.g., virustotal, abuseipdb)")
    input_field: str = Field(
        ..., description="Alert field to pass as input (e.g., source_ip, alert_id)"
    )
    timeout: int = Field(default=10, description="Execution timeout in seconds")
    retries: int = Field(default=3, description="Maximum retry attempts on failure")
    on_result: list[Condition] = Field(
        default_factory=list, description="Conditional actions on result"
    )

    @field_validator("timeout")
    def validate_timeout(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("timeout must be > 0")
        return v

    @field_validator("retries")
    def validate_retries(cls, v: int) -> int:
        if v < 0:
            raise ValueError("retries must be >= 0")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "enrich_ip",
                "connector": "virustotal",
                "input_field": "source_ip",
                "timeout": 10,
                "retries": 3,
                "on_result": [
                    {"if_expr": "score > 70", "then": "escalate"},
                    {"then": "continue"},
                ],
            }
        }
    )


class Playbook(BaseModel):
    """
    Complete playbook definition.
    Represents orchestration logic triggered by alerts.
    """

    name: str = Field(..., description="Playbook name (unique identifier)")
    trigger_alert_type: str = Field(..., description="Alert type that triggers this playbook")
    min_severity: Literal["low", "medium", "high", "critical"] = Field(
        default="medium", description="Minimum severity to trigger"
    )
    steps: list[Step] = Field(..., description="Ordered list of execution steps")

    @field_validator("steps")
    def validate_steps(cls, v: list[Step]) -> list[Step]:
        if not v:
            raise ValueError("Playbook must have at least one step")

        # Validate step IDs are unique
        step_ids = [s.id for s in v]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("Step IDs must be unique within a playbook")

        return v

    @field_validator("name")
    def validate_name(cls, v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError("Playbook name cannot be empty")
        return v.strip()

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "phishing_triage",
                "trigger_alert_type": "phishing",
                "min_severity": "medium",
                "steps": [
                    {
                        "id": "enrich_ip",
                        "connector": "virustotal",
                        "input_field": "source_ip",
                        "timeout": 10,
                        "retries": 3,
                        "on_result": [
                            {"if_expr": "score > 70", "then": "escalate"},
                            {"then": "continue"},
                        ],
                    },
                    {
                        "id": "check_reputation",
                        "connector": "abuseipdb",
                        "input_field": "source_ip",
                        "timeout": 10,
                        "retries": 2,
                        "on_result": [
                            {"if_expr": "abuse_score > 50", "then": "escalate"},
                            {"then": "continue"},
                        ],
                    },
                    {
                        "id": "create_ticket",
                        "connector": "mock_jira",
                        "input_field": "alert_id",
                        "timeout": 5,
                        "retries": 1,
                        "on_result": [{"then": "close"}],
                    },
                ],
            }
        }
    )
