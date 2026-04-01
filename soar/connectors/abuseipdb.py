"""AbuseIPDB connector for IP abuse reporting and checking."""

import logging
from typing import Any, ClassVar

import httpx

from soar.config import settings
from soar.connectors.base import BaseConnector, ConnectorResult

logger = logging.getLogger(__name__)


class AbuseIPDBConnector(BaseConnector):
    """
    AbuseIPDB connector for IP abuse reputation.
    Makes real async HTTP calls to api.abuseipdb.com.
    """

    name: ClassVar[str] = "abuseipdb"
    BASE_URL = "https://api.abuseipdb.com/api/v2"

    async def execute(self, params: dict[str, Any]) -> ConnectorResult:
        """
        Check an IP's abuse confidence score on AbuseIPDB.

        Args:
            params: Must contain {"ip": "192.168.1.1"}

        Returns:
            ConnectorResult with abuse_score (0-100)
        """
        if not settings.ABUSEIPDB_API_KEY:
            return ConnectorResult(
                success=False,
                error="ABUSEIPDB_API_KEY not configured",
            )

        ip = params.get("ip")
        if not ip:
            return ConnectorResult(
                success=False,
                error="params must contain 'ip'",
            )

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                url = f"{self.BASE_URL}/check"
                headers = {
                    "Key": settings.ABUSEIPDB_API_KEY,
                    "Accept": "application/json",
                }
                query_params = {
                    "ipAddress": ip,
                    "maxAgeInDays": 90,
                }

                logger.debug(f"Calling AbuseIPDB: {url} for {ip}")
                response = await client.get(url, headers=headers, params=query_params)

                if response.status_code != 200:
                    return ConnectorResult(
                        success=False,
                        error=f"HTTP {response.status_code}: {response.text}",
                    )

                data = response.json()
                abuse_data = data.get("data", {})

                abuse_score = abuse_data.get("abuseConfidenceScore", 0)
                total_reports = abuse_data.get("totalReports", 0)

                result_data = {
                    "ip": ip,
                    "abuse_score": abuse_score,
                    "total_reports": total_reports,
                    "is_whitelisted": abuse_data.get("isWhitelisted", False),
                    "last_reported_at": abuse_data.get("lastReportedAt"),
                }

                logger.debug(f"AbuseIPDB result: abuse_score={abuse_score} for {ip}")

                return ConnectorResult(
                    success=True,
                    data=result_data,
                    raw_response=data,
                )

        except httpx.TimeoutException:
            return ConnectorResult(
                success=False,
                error=f"AbuseIPDB timeout for {ip}",
            )
        except httpx.HTTPError as error:
            return ConnectorResult(
                success=False,
                error=f"AbuseIPDB HTTP error: {str(error)}",
            )
        except Exception as error:
            logger.error(f"AbuseIPDB error: {error}")
            return ConnectorResult(
                success=False,
                error=f"AbuseIPDB error: {str(error)}",
            )

    async def health_check(self) -> bool:
        """Check AbuseIPDB API connectivity."""
        if not settings.ABUSEIPDB_API_KEY:
            return False

        try:
            async with httpx.AsyncClient(timeout=5) as client:
                url = f"{self.BASE_URL}/check"
                headers = {
                    "Key": settings.ABUSEIPDB_API_KEY,
                    "Accept": "application/json",
                }
                response = await client.get(
                    url,
                    headers=headers,
                    params={"ipAddress": "8.8.8.8", "maxAgeInDays": 90},
                )
                return response.status_code == 200
        except Exception:
            return False
