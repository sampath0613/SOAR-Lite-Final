"""VirusTotal connector for IP and domain reputation analysis."""

import logging
from typing import Any, ClassVar

import httpx

from soar.config import settings
from soar.connectors.base import BaseConnector, ConnectorResult

logger = logging.getLogger(__name__)


class VirusTotalConnector(BaseConnector):
    """
    VirusTotal connector for IP/domain reputation analysis.
    Makes real async HTTP calls to api.virustotal.com.
    """

    name: ClassVar[str] = "virustotal"
    BASE_URL = "https://www.virustotal.com/api/v3"

    async def execute(self, params: dict[str, Any]) -> ConnectorResult:
        """
        Scan an IP or domain on VirusTotal.

        Args:
            params: Must contain {"ip": "8.8.8.8"} or {"domain": "example.com"}

        Returns:
            ConnectorResult with score (0-100+, number of malicious detections)
        """
        if not settings.VIRUSTOTAL_API_KEY:
            return ConnectorResult(
                success=False,
                error="VIRUSTOTAL_API_KEY not configured",
            )

        ip = params.get("ip")
        domain = params.get("domain")

        if not ip and not domain:
            return ConnectorResult(
                success=False,
                error="params must contain 'ip' or 'domain'",
            )

        target = ip or domain
        endpoint = f"/ip_addresses/{ip}" if ip else f"/domains/{domain}"

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                headers = {"x-apikey": settings.VIRUSTOTAL_API_KEY}
                url = f"{self.BASE_URL}{endpoint}"

                logger.debug(f"Calling VirusTotal: {url}")
                response = await client.get(url, headers=headers)

                if response.status_code == 404:
                    return ConnectorResult(
                        success=True,
                        data={"target": target, "score": 0, "note": "Target not found"},
                        raw_response=response.json() if response.text else None,
                    )

                if response.status_code != 200:
                    return ConnectorResult(
                        success=False,
                        error=f"HTTP {response.status_code}: {response.text}",
                    )

                data = response.json()
                attrs = data.get("data", {}).get("attributes", {})
                last_analysis_stats = attrs.get("last_analysis_stats", {})

                # Extract malicious detections as score
                score = last_analysis_stats.get("malicious", 0)

                result_data = {
                    "target": target,
                    "score": score,
                    "detections": {
                        "malicious": last_analysis_stats.get("malicious", 0),
                        "suspicious": last_analysis_stats.get("suspicious", 0),
                        "undetected": last_analysis_stats.get("undetected", 0),
                    },
                    "last_analysis_date": attrs.get("last_analysis_date"),
                }

                logger.debug(f"VirusTotal result: score={score} for {target}")

                return ConnectorResult(
                    success=True,
                    data=result_data,
                    raw_response=data,
                )

        except httpx.TimeoutException:
            return ConnectorResult(
                success=False,
                error=f"VirusTotal timeout for {target}",
            )
        except httpx.HTTPError as error:
            return ConnectorResult(
                success=False,
                error=f"VirusTotal HTTP error: {str(error)}",
            )
        except Exception as error:
            logger.error(f"VirusTotal error: {error}")
            return ConnectorResult(
                success=False,
                error=f"VirusTotal error: {str(error)}",
            )

    async def health_check(self) -> bool:
        """Check VirusTotal API connectivity."""
        if not settings.VIRUSTOTAL_API_KEY:
            return False

        try:
            async with httpx.AsyncClient(timeout=5) as client:
                headers = {"x-apikey": settings.VIRUSTOTAL_API_KEY}
                response = await client.get(
                    f"{self.BASE_URL}/ip_addresses/8.8.8.8",
                    headers=headers,
                )
                return response.status_code in [200, 404]
        except Exception:
            return False
