"""Unit tests for Slack connector behavior."""

from unittest.mock import patch

import httpx
import pytest
import respx

from soar.connectors.slack import SlackConnector


@pytest.mark.asyncio
async def test_slack_execute_requires_configuration(monkeypatch):
    """Connector should fail fast when no Slack credentials are configured."""
    from soar.connectors import slack as slack_module

    monkeypatch.setattr(slack_module.settings, "SLACK_WEBHOOK_URL", "")
    monkeypatch.setattr(slack_module.settings, "SLACK_BOT_TOKEN", "")

    result = await SlackConnector().execute({"message": "hello"})

    assert result.success is False
    assert "not configured" in result.error


@pytest.mark.asyncio
async def test_slack_execute_requires_message(monkeypatch):
    """Connector should require a message payload."""
    from soar.connectors import slack as slack_module

    monkeypatch.setattr(slack_module.settings, "SLACK_WEBHOOK_URL", "https://hooks.slack.test/abc")
    monkeypatch.setattr(slack_module.settings, "SLACK_BOT_TOKEN", "")

    result = await SlackConnector().execute({})

    assert result.success is False
    assert "message" in result.error


@pytest.mark.asyncio
async def test_slack_webhook_success(monkeypatch):
    """Webhook mode should return success on HTTP 200."""
    from soar.connectors import slack as slack_module

    webhook = "https://hooks.slack.test/services/test"
    monkeypatch.setattr(slack_module.settings, "SLACK_WEBHOOK_URL", webhook)
    monkeypatch.setattr(slack_module.settings, "SLACK_BOT_TOKEN", "")

    with respx.mock:
        respx.post(webhook).mock(return_value=httpx.Response(200, text="ok"))
        result = await SlackConnector().execute({"message": "alert"})

    assert result.success is True
    assert result.data["message_sent"] is True


@pytest.mark.asyncio
async def test_slack_webhook_http_error(monkeypatch):
    """Webhook mode should surface HTTP errors."""
    from soar.connectors import slack as slack_module

    webhook = "https://hooks.slack.test/services/test"
    monkeypatch.setattr(slack_module.settings, "SLACK_WEBHOOK_URL", webhook)
    monkeypatch.setattr(slack_module.settings, "SLACK_BOT_TOKEN", "")

    with respx.mock:
        respx.post(webhook).mock(return_value=httpx.Response(400, text="bad request"))
        result = await SlackConnector().execute({"message": "alert"})

    assert result.success is False
    assert "HTTP 400" in result.error


@pytest.mark.asyncio
async def test_slack_webhook_timeout(monkeypatch):
    """Webhook mode should handle request timeouts."""
    from soar.connectors import slack as slack_module

    webhook = "https://hooks.slack.test/services/test"
    monkeypatch.setattr(slack_module.settings, "SLACK_WEBHOOK_URL", webhook)
    monkeypatch.setattr(slack_module.settings, "SLACK_BOT_TOKEN", "")

    with respx.mock:
        respx.post(webhook).mock(side_effect=httpx.TimeoutException("timeout"))
        result = await SlackConnector().execute({"message": "alert"})

    assert result.success is False
    assert "timeout" in result.error.lower()


@pytest.mark.asyncio
async def test_slack_bot_success(monkeypatch):
    """Bot-token mode should return message metadata on success."""
    from soar.connectors import slack as slack_module

    monkeypatch.setattr(slack_module.settings, "SLACK_WEBHOOK_URL", "")
    monkeypatch.setattr(slack_module.settings, "SLACK_BOT_TOKEN", "xoxb-test")

    with respx.mock:
        respx.post("https://slack.com/api/chat.postMessage").mock(
            return_value=httpx.Response(
                200,
                json={"ok": True, "ts": "123.456", "channel": "C123"},
            )
        )
        result = await SlackConnector().execute({"message": "hello", "channel": "#soc"})

    assert result.success is True
    assert result.data["message_ts"] == "123.456"


@pytest.mark.asyncio
async def test_slack_bot_api_error(monkeypatch):
    """Bot-token mode should surface Slack API failures."""
    from soar.connectors import slack as slack_module

    monkeypatch.setattr(slack_module.settings, "SLACK_WEBHOOK_URL", "")
    monkeypatch.setattr(slack_module.settings, "SLACK_BOT_TOKEN", "xoxb-test")

    with respx.mock:
        respx.post("https://slack.com/api/chat.postMessage").mock(
            return_value=httpx.Response(200, json={"ok": False, "error": "invalid_auth"})
        )
        result = await SlackConnector().execute({"message": "hello", "channel": "#soc"})

    assert result.success is False
    assert "invalid_auth" in result.error


@pytest.mark.asyncio
async def test_slack_execute_handles_unexpected_exception(monkeypatch):
    """Top-level execute should convert unexpected exceptions into ConnectorResult."""
    from soar.connectors import slack as slack_module

    monkeypatch.setattr(slack_module.settings, "SLACK_WEBHOOK_URL", "https://hooks.slack.test/abc")
    monkeypatch.setattr(slack_module.settings, "SLACK_BOT_TOKEN", "")

    connector = SlackConnector()
    with patch.object(connector, "_send_via_webhook", side_effect=RuntimeError("boom")):
        result = await connector.execute({"message": "hello"})

    assert result.success is False
    assert "boom" in result.error


@pytest.mark.asyncio
async def test_slack_health_check_bot_and_no_config(monkeypatch):
    """health_check should return False without config and True for successful bot auth test."""
    from soar.connectors import slack as slack_module

    connector = SlackConnector()

    monkeypatch.setattr(slack_module.settings, "SLACK_WEBHOOK_URL", "")
    monkeypatch.setattr(slack_module.settings, "SLACK_BOT_TOKEN", "")
    assert await connector.health_check() is False

    monkeypatch.setattr(slack_module.settings, "SLACK_BOT_TOKEN", "xoxb-test")
    with respx.mock:
        respx.get("https://slack.com/api/auth.test").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        assert await connector.health_check() is True
