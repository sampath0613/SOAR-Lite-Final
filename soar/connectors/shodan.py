"""Shodan connector for internet-wide device scanning and reconnaissance."""

import logging
from typing import Any, ClassVar

import httpx

from soar.config import settings
from soar.connectors.base import BaseConnector, ConnectorResult

logger = logging.getLogger(__name__)


class ShodanConnector(BaseConnector):
    """
    Shodan connector for internet device reconnaissance.
    Makes real async HTTP calls to api.shodan.io.
    """

    name: ClassVar[str] = "shodan"
    BASE_URL = "https://api.shodan.io"

    async def execute(self, params: dict[str, Any]) -> ConnectorResult:
        """
        Query Shodan for information about an IP.

        Args:
            params: Must contain {"ip": "8.8.8.8"}

        Returns:
            ConnectorResult with open ports, services, and host info
        """
        if not settings.SHODAN_API_KEY:
            return ConnectorResult(
                success=False,
                error="SHODAN_API_KEY not configured",
            )

        ip = params.get("ip")
        if not ip:
            return ConnectorResult(
                success=False,
                error="params must contain 'ip'",
            )

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                url = f"{self.BASE_URL}/shodan/host/{ip}"
                query_params = {"key": settings.SHODAN_API_KEY}

                logger.debug(f"Calling Shodan: {url}")
                response = await client.get(url, params=query_params)

                if response.status_code == 404:
                    return ConnectorResult(
                        success=True,
                        data={"ip": ip, "found": False},
                        raw_response=None,
                    )

                if response.status_code != 200:
                    return ConnectorResult(
                        success=False,
                        error=f"HTTP {response.status_code}: {response.text}",
                    )

                data = response.json()

                result_data = {
                    "ip": ip,
                    "found": True,
                    "ports": data.get("ports", []),
                    "protocols": data.get("protocols", []),
                    "hostnames": data.get("hostnames", []),
                    "org": data.get("org", "unknown"),
                    "country": data.get("country_name", "unknown"),
                    "port_count": len(data.get("ports", [])),
                }

                logger.debug(
                    f"Shodan result: {result_data['port_count']} open ports for {ip}"
                )

                return ConnectorResult(
                    success=True,
                    data=result_data,
                    raw_response=data,
                )

        except httpx.TimeoutException:
            return ConnectorResult(
                success=False,
                error=f"Shodan timeout for {ip}",
            )
        except httpx.HTTPError as error:
            return ConnectorResult(
                success=False,
                error=f"Shodan HTTP error: {str(error)}",
            )
        except Exception as error:
            logger.error(f"Shodan error: {error}")
            return ConnectorResult(
                success=False,
                error=f"Shodan error: {str(error)}",
            )

    async def health_check(self) -> bool:
        """Check Shodan API connectivity."""
        if not settings.SHODAN_API_KEY:
            return False

        try:
            async with httpx.AsyncClient(timeout=5) as client:
                url = f"{self.BASE_URL}/shodan/host/8.8.8.8"
                response = await client.get(
                    url,
                    params={"key": settings.SHODAN_API_KEY},
                )
                return response.status_code in [200, 404]
        except Exception:
            return False
