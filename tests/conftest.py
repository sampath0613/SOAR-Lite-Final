"""Test configuration and fixtures for SOAR-Lite."""

import asyncio
import json
from datetime import datetime, timezone
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from soar.main import create_app, APP_STATE
from soar.models.incident import Base, Incident, StepExecution
from soar.models.alert import Alert


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def test_db() -> AsyncGenerator[AsyncSession, None]:
    """Create an in-memory SQLite test database."""
    # Create in-memory engine
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Create session factory
    async_session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Provide session
    async with async_session_factory() as session:
        yield session

    # Cleanup
    await engine.dispose()


@pytest_asyncio.fixture
async def test_client(test_db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test FastAPI client with test database."""
    app = create_app()

    # Override database dependency
    from soar.db.database import get_db

    request_session_factory = async_sessionmaker(
        bind=test_db.bind,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def override_get_db():
        async with request_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    # Mock playbooks
    APP_STATE["playbooks"] = {
        "phishing_triage": pytest.MockPlaybook(
            name="phishing_triage",
            trigger_alert_type="phishing",
            min_severity="low",
        ),
        "malware_detection": pytest.MockPlaybook(
            name="malware_detection",
            trigger_alert_type="malware",
            min_severity="low",
        ),
        "bruteforce_response": pytest.MockPlaybook(
            name="bruteforce_response",
            trigger_alert_type="bruteforce",
            min_severity="low",
        ),
        "suspicious_domain": pytest.MockPlaybook(
            name="suspicious_domain",
            trigger_alert_type="suspicious_domain",
            min_severity="low",
        ),
        "c2_detection": pytest.MockPlaybook(
            name="c2_detection",
            trigger_alert_type="c2_communication",
            min_severity="low",
        ),
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def sample_alert() -> Alert:
    """Create a sample alert for testing."""
    return Alert(
        alert_id="test-alert-001",
        alert_type="phishing",
        severity="high",
        source_ip="192.168.1.100",
        destination_ip="10.0.0.1",
        timestamp=datetime.now(timezone.utc),
        raw_payload={"email": "attacker@evil.com"},
        source_system="mock",
    )


@pytest_asyncio.fixture
async def sample_incident(test_db: AsyncSession, sample_alert: Alert) -> Incident:
    """Create a sample incident for testing."""
    from soar.db.crud import create_incident

    incident = await create_incident(
        db=test_db,
        alert_id=sample_alert.alert_id,
        playbook_name="phishing_triage",
        raw_alert_json=sample_alert.model_dump_json(),
    )
    return incident


@pytest_asyncio.fixture
async def sample_step_execution(test_db: AsyncSession, sample_incident: Incident) -> StepExecution:
    """Create a sample step execution for testing."""
    from soar.db.crud import create_step_execution

    step_exec = await create_step_execution(
        db=test_db,
        incident_id=sample_incident.id,
        step_id="test_step",
        connector_name="mock_jira",
        input_params_json=json.dumps({"alert_id": sample_incident.alert_id}),
    )
    return step_exec


# Mock objects for testing
class MockPlaybook:
    """Mock playbook for testing."""

    def __init__(self, name: str, trigger_alert_type: str, min_severity: str):
        self.name = name
        self.trigger_alert_type = trigger_alert_type
        self.min_severity = min_severity
        self.steps = [
            MockStep(
                id="test_step_1",
                connector="mock_jira",
                input_field="source_ip",
            ),
            MockStep(
                id="test_step_2",
                connector="mock_jira",
                input_field="alert_id",
            ),
        ]


class MockStep:
    """Mock step for testing."""

    def __init__(self, id: str, connector: str, input_field: str):
        self.id = id
        self.connector = connector
        self.input_field = input_field
        self.timeout = 10
        self.retries = 3
        self.on_result = [MockCondition(if_expr=None, then="close")]


class MockCondition:
    """Mock condition for testing."""

    def __init__(self, if_expr: str = None, then: str = "continue"):
        self.if_expr = if_expr
        self.then = then


# Make MockPlaybook available in pytest namespace
pytest.MockPlaybook = MockPlaybook
pytest.MockStep = MockStep
pytest.MockCondition = MockCondition
