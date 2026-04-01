"""Unit tests for database session manager."""

import pytest

from soar.db.database import DatabaseManager, get_db


@pytest.mark.asyncio
async def test_get_session_before_init_raises():
    """get_session should fail before manager initialization."""
    manager = DatabaseManager("sqlite+aiosqlite:///:memory:")

    with pytest.raises(RuntimeError):
        async for _ in manager.get_session():
            pass


@pytest.mark.asyncio
async def test_database_manager_init_session_close():
    """Manager should initialize engine, yield session, and close cleanly."""
    manager = DatabaseManager("sqlite+aiosqlite:///:memory:")
    await manager.init()

    yielded = False
    async for session in manager.get_session():
        assert session is not None
        yielded = True
        break

    assert yielded is True
    await manager.close()


@pytest.mark.asyncio
async def test_get_db_dependency_uses_configured_manager(monkeypatch):
    """get_db dependency should yield sessions from the active global manager."""
    import soar.db.database as db_module

    manager = DatabaseManager("sqlite+aiosqlite:///:memory:")
    await manager.init()

    monkeypatch.setattr(db_module, "db_manager", manager)

    yielded = False
    async for session in get_db():
        assert session.bind is not None
        yielded = True
        break

    assert yielded is True
    await manager.close()
