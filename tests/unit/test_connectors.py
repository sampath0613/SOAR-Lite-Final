"""Unit tests for connector implementations."""


import httpx
import pytest
import respx
from unittest.mock import patch

from soar.connectors.abuseipdb import AbuseIPDBConnector
from soar.connectors.base import ConnectorResult
from soar.connectors.mock_jira import MockJiraConnector
from soar.connectors.shodan import ShodanConnector
from soar.connectors.virustotal import VirusTotalConnector


@pytest.fixture
def mock_api_settings():
    """Mock the settings object to provide test API keys."""
    with patch('soar.connectors.virustotal.settings') as mock_vt_settings, \
         patch('soar.connectors.abuseipdb.settings') as mock_abuse_settings, \
         patch('soar.connectors.shodan.settings') as mock_shodan_settings:
        mock_vt_settings.VIRUSTOTAL_API_KEY = "test-vt-key"
        mock_abuse_settings.ABUSEIPDB_API_KEY = "test-abuse-key"
        mock_shodan_settings.SHODAN_API_KEY = "test-shodan-key"
        yield


@pytest.mark.asyncio
async def test_virustotal_connector_success(mock_api_settings):
    """Test: VirusTotal connector with malicious IP."""
    connector = VirusTotalConnector()

    # Mock HTTP response
    with respx.mock:
        respx.get("https://www.virustotal.com/api/v3/ip_addresses/192.168.1.100").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {
                        "attributes": {
                            "last_analysis_stats": {"malicious": 15, "suspicious": 2},
                            "last_analysis_date": 1234567890,
                        }
                    }
                },
            )
        )

        result = await connector.execute({"ip": "192.168.1.100"})

    assert result.success is True
    assert result.data["score"] == 15
    assert result.error is None


@pytest.mark.asyncio
async def test_virustotal_connector_not_found(mock_api_settings):
    """Test: VirusTotal connector with unknown IP returns score 0."""
    connector = VirusTotalConnector()

    with respx.mock:
        respx.get("https://www.virustotal.com/api/v3/ip_addresses/192.168.1.100").mock(
            return_value=httpx.Response(404)
        )

        result = await connector.execute({"ip": "192.168.1.100"})

    assert result.success is True
    assert result.data["score"] == 0


@pytest.mark.asyncio
async def test_virustotal_connector_rate_limit(mock_api_settings):
    """Test: VirusTotal connector handles rate limit gracefully."""
    connector = VirusTotalConnector()

    with respx.mock:
        respx.get("https://www.virustotal.com/api/v3/ip_addresses/192.168.1.100").mock(
            return_value=httpx.Response(429)
        )

        result = await connector.execute({"ip": "192.168.1.100"})

    assert result.success is False
    assert "429" in result.error or "rate" in result.error.lower()


@pytest.mark.asyncio
async def test_abuseipdb_connector_success(mock_api_settings):
    """Test: AbuseIPDB connector with abusive IP."""
    connector = AbuseIPDBConnector()

    with respx.mock:
        respx.get("https://api.abuseipdb.com/api/v2/check").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {
                        "abuseConfidenceScore": 75,
                        "totalReports": 10,
                        "isWhitelisted": False,
                    }
                },
            )
        )

        result = await connector.execute({"ip": "192.168.1.100"})

    assert result.success is True
    assert result.data["abuse_score"] == 75


@pytest.mark.asyncio
async def test_abuseipdb_connector_clean_ip(mock_api_settings):
    """Test: AbuseIPDB connector with clean IP returns low score."""
    connector = AbuseIPDBConnector()

    with respx.mock:
        respx.get("https://api.abuseipdb.com/api/v2/check").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {
                        "abuseConfidenceScore": 0,
                        "totalReports": 0,
                        "isWhitelisted": False,
                    }
                },
            )
        )

        result = await connector.execute({"ip": "8.8.8.8"})

    assert result.success is True
    assert result.data["abuse_score"] == 0


@pytest.mark.asyncio
async def test_shodan_connector_success(mock_api_settings):
    """Test: Shodan connector returns device info."""
    connector = ShodanConnector()

    with respx.mock:
        respx.get("https://api.shodan.io/shodan/host/192.168.1.100").mock(
            return_value=httpx.Response(
                200,
                json={
                    "ip_str": "192.168.1.100",
                    "ports": [22, 80, 443],
                    "org": "Example Corp",
                    "country_name": "United States",
                },
            )
        )

        result = await connector.execute({"ip": "192.168.1.100"})

    assert result.success is True
    assert result.data["ports"] == [22, 80, 443]
    assert result.data["org"] == "Example Corp"


@pytest.mark.asyncio
async def test_shodan_connector_not_found():
    """Test: Shodan connector handles not found gracefully."""
    connector = ShodanConnector()

    with respx.mock:
        respx.get("https://api.shodan.io/shodan/host/192.168.1.100").mock(
            return_value=httpx.Response(404)
        )

        result = await connector.execute({"ip": "192.168.1.100"})

    assert result.success is False


@pytest.mark.asyncio
async def test_mockjira_connector_creates_ticket():
    """Test: MockJira connector generates ticket ID (no HTTP)."""
    connector = MockJiraConnector()

    result = await connector.execute({"incident": "test"})

    assert result.success is True
    assert "ticket_id" in result.data
    assert result.data["ticket_id"].startswith("SOAR-")


@pytest.mark.asyncio
async def test_mockjira_connector_health_check():
    """Test: MockJira health check always returns True."""
    connector = MockJiraConnector()

    # Since MockJira doesn't do HTTP, it should always be healthy
    healthy = await connector.health_check()

    assert healthy is True


@pytest.mark.asyncio
async def test_connector_result_serialization():
    """Test: ConnectorResult serializes to JSON properly."""

    result = ConnectorResult(
        success=True,
        data={"score": 85, "found": True},
        error=None,
    )

    # Should be JSON serializable
    json_str = result.model_dump_json()
    assert '"success":true' in json_str
    assert '"score":85' in json_str
