"""Slack connector for notifications and incident reporting."""

import logging
from typing import Any, ClassVar

import httpx

from soar.config import settings
from soar.connectors.base import BaseConnector, ConnectorResult

logger = logging.getLogger(__name__)


class SlackConnector(BaseConnector):
    """
    Slack connector for sending notifications and alerts.
    Uses either incoming webhooks or bot tokens.
    """

    name: ClassVar[str] = "slack"

    async def execute(self, params: dict[str, Any]) -> ConnectorResult:
        """
        Send a message to Slack.

        Args:
            params: Must contain:
                - "message": message text
                - "channel": optional channel name or ID (e.g., "#security" or "C123...")
                - "user_id": optional Slack user ID for DM

        Returns:
            ConnectorResult with message_ts (timestamp)
        """
        if not settings.SLACK_WEBHOOK_URL and not settings.SLACK_BOT_TOKEN:
            return ConnectorResult(
                success=False,
                error="SLACK_WEBHOOK_URL or SLACK_BOT_TOKEN not configured",
            )

        message = params.get("message")
        if not message:
            return ConnectorResult(
                success=False,
                error="params must contain 'message'",
            )

        try:
            # Try webhook first (simple, doesn't require bot token)
            if settings.SLACK_WEBHOOK_URL:
                return await self._send_via_webhook(message)

            # Fallback to bot token
            if settings.SLACK_BOT_TOKEN:
                channel = params.get("channel", "#general")
                return await self._send_via_bot(message, channel)

        except Exception as error:
            logger.error(f"Slack error: {error}")
            return ConnectorResult(
                success=False,
                error=f"Slack error: {str(error)}",
            )

    async def _send_via_webhook(self, message: str) -> ConnectorResult:
        """Send message via incoming webhook."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                payload = {"text": message}

                logger.debug("Sending Slack webhook message")
                response = await client.post(
                    settings.SLACK_WEBHOOK_URL,
                    json=payload,
                )

                if response.status_code != 200:
                    return ConnectorResult(
                        success=False,
                        error=f"Slack webhook HTTP {response.status_code}: {response.text}",
                    )

                return ConnectorResult(
                    success=True,
                    data={
                        "message_sent": True,
                        "channel": "webhook",
                        "note": "Webhook does not return message_ts",
                    },
                )

        except httpx.TimeoutException:
            return ConnectorResult(
                success=False,
                error="Slack webhook timeout",
            )
        except Exception as error:
            return ConnectorResult(
                success=False,
                error=f"Slack webhook error: {str(error)}",
            )

    async def _send_via_bot(self, message: str, channel: str) -> ConnectorResult:
        """Send message via bot token."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                headers = {
                    "Authorization": f"Bearer {settings.SLACK_BOT_TOKEN}",
                    "Content-Type": "application/json",
                }

                # Determine if sending to channel or user DM
                if channel.startswith("U") or "@" in channel:
                    # DM to user
                    payload = {
                        "channel": channel,
                        "text": message,
                    }
                else:
                    # Channel message
                    payload = {
                        "channel": channel,
                        "text": message,
                    }

                logger.debug(f"Sending Slack bot message to {channel}")
                response = await client.post(
                    "https://slack.com/api/chat.postMessage",
                    headers=headers,
                    json=payload,
                )

                result = response.json()

                if not result.get("ok"):
                    error_msg = result.get("error", "Unknown error")
                    return ConnectorResult(
                        success=False,
                        error=f"Slack API error: {error_msg}",
                    )

                return ConnectorResult(
                    success=True,
                    data={
                        "message_ts": result.get("ts"),
                        "channel": result.get("channel"),
                        "message_sent": True,
                    },
                    raw_response=result,
                )

        except httpx.TimeoutException:
            return ConnectorResult(
                success=False,
                error="Slack bot timeout",
            )
        except Exception as error:
            return ConnectorResult(
                success=False,
                error=f"Slack bot error: {str(error)}",
            )

    async def health_check(self) -> bool:
        """Check Slack connectivity."""
        if not settings.SLACK_WEBHOOK_URL and not settings.SLACK_BOT_TOKEN:
            return False

        try:
            if settings.SLACK_BOT_TOKEN:
                async with httpx.AsyncClient(timeout=5) as client:
                    headers = {
                        "Authorization": f"Bearer {settings.SLACK_BOT_TOKEN}",
                    }
                    response = await client.get(
                        "https://slack.com/api/auth.test",
                        headers=headers,
                    )
                    result = response.json()
                    return result.get("ok", False)
            else:
                # Webhook is harder to test without posting
                return True
        except Exception:
            return False
