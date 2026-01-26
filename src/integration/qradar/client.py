"""
QRadar Integration Module

Provides IBM QRadar SIEM integration for sending security events
and receiving analyst feedback.
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, TypedDict

import httpx
from pydantic import BaseModel, Field

from src.integration.common.base import BaseIntegration, HealthStatus, IntegrationConfig

logger = logging.getLogger(__name__)


@dataclass
class QRadarConfig(IntegrationConfig):
    """QRadar-specific configuration."""

    host: str = "qradar.example.com"
    token: str = ""
    api_version: str = "12.0"
    verify_ssl: bool = True
    protocol: str = "https"

    # Ariel Query config
    default_timeout: int = 60
    max_results: int = 1000

    # Offense config
    offense_types: dict[str, int] = field(
        default_factory=lambda: {
            "username": 0,
            "sourceip": 1,
            "destinationip": 2,
            "hostname": 3,
            "macaddress": 4,
            "application": 5,
            "netmap": 6,
            "vulnerability": 7,
            "identity": 8,
            "behavioral": 9,
        }
    )


class LEEFEvent(BaseModel):
    """Log Event Extended Format (LEEF) event for QRadar."""

    version: str = "LEEF:1.0"
    vendor: str = "AI-Log-Filter"
    product: str = "AI-Log-Filter"
    version_product: str = "1.0"

    # Required fields
    name: str
    severity: int = Field(ge=0, le=10, default=5)

    # Optional fields
    message_id: str | None = None
    signature_id: str | None = None
    source_host: str | None = None
    source_ip: str | None = None
    source_port: int | None = None
    dest_host: str | None = None
    dest_ip: str | None = None
    dest_port: int | None = None
    username: str | None = None
    url: str | None = None
    file_path: str | None = None
    process_id: str | None = None
    process_name: str | None = None
    protocol: str | None = None
    bytes_in: int | None = None
    bytes_out: int | None = None
    count: int | None = None

    # Custom extension fields
    extensions: dict[str, str] = Field(default_factory=dict)

    # Category mapping
    category_map: dict[str, int] = field(
        default_factory=lambda: {
            "critical": 10,
            "high": 8,
            "medium": 6,
            "low": 4,
            "info": 2,
        }
    )

    def to_leef(self) -> str:
        """Convert to LEEF string format."""
        parts = [
            self.version,
            self.vendor,
            self.product,
            self.version_product,
            self.severity,
        ]

        # Add optional fields
        if self.message_id:
            parts.append(self.message_id)
        else:
            parts.append("AI-Log-Filter-Event")

        # Build attributes dict
        attrs = {
            "src": self.source_ip,
            "dst": self.dest_ip,
            "spt": self.source_port,
            "dpt": self.dest_port,
            "shost": self.source_host,
            "dhost": self.dest_host,
            "usrName": self.username,
            "url": self.url,
            "file": self.file_path,
            "procId": self.process_id,
            "procName": self.process_name,
            "proto": self.protocol,
            "bytesIn": str(self.bytes_in) if self.bytes_in else None,
            "bytesOut": str(self.bytes_out) if self.bytes_out else None,
            "cnt": str(self.count) if self.count else None,
        }

        # Add custom extensions
        attrs.update(self.extensions)

        # Add category-based severity
        if self.name:
            name_lower = self.name.lower()
            for cat, sev in self.category_map.items():
                if cat in name_lower:
                    attrs["severity"] = str(sev)
                    break

        # Filter None values
        attrs = {k: v for k, v in attrs.items() if v is not None}

        # Build attribute string
        attr_parts = [f"{k}={v}" for k, v in attrs.items()]
        attr_str = "\t".join(attr_parts)

        # Escape tab and newlines in values
        attr_str = attr_str.replace("\n", "\\n").replace("\t", "\\t")

        parts.append(attr_str)

        return "\t".join(parts)


class QRadarEvent(TypedDict):
    """QRadar event format."""

    sourceip: str | None
    destinationip: str | None
    sourceport: int | None
    destinationport: int | None
    username: str | None
    hostname: str | None
    qid: int | None
    severity: int | None
    content: str | None
    device_time: str | None
    logsourceid: int | None
    facility: int | None


class QRadarIntegration(BaseIntegration):
    """
    QRadar SIEM integration for sending security events.
    """

    def __init__(self, config: QRadarConfig):
        super().__init__("qradar", config)
        self.config = config
        self._client: httpx.AsyncClient | None = None
        self._base_url: str | None = None

    def _create_client(self) -> httpx.AsyncClient:
        """Create HTTP client for QRadar API."""
        return httpx.AsyncClient(
            timeout=httpx.Timeout(self.config.timeout),
            verify=self.config.verify_ssl,
            headers={
                "SEC": self.config.token,
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )

    async def connect(self) -> bool:
        """Establish QRadar API connection."""
        try:
            self._client = self._create_client()
            self._base_url = (
                f"{self.config.protocol}://{self.config.host}/api/{self.config.api_version}"
            )

            # Test connection
            response = await self._client.get(f"{self._base_url}/system/info", timeout=30.0)

            if response.status_code == 200:
                info = response.json()
                logger.info(
                    f"Connected to QRadar {info.get('version', 'unknown')}",
                    extra={"qradar_host": self.config.host, "version": info.get("version")},
                )
                return True
            else:
                logger.error(f"QRadar connection failed: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"QRadar connection error: {e}")
            return False

    async def disconnect(self) -> None:
        """Close QRadar connection."""
        if self._client:
            await self._client.aclose()
            logger.info("QRadar connection closed")

    async def send_event(
        self, event: LEEFEvent | dict[str, Any], log_source_id: int | None = None
    ) -> bool:
        """
        Send a single event to QRadar via the Event API.

        Args:
            event: LEEFEvent or dict containing event data
            log_source_id: Optional log source ID

        Returns:
            True if successful, False otherwise
        """
        if not self._client:
            raise RuntimeError("QRadar client not connected")

        try:
            # Convert to LEEF if needed
            if isinstance(event, dict):
                leef_event = LEEFEvent(**event)
            else:
                leef_event = event

            leef_string = leef_event.to_leef()

            # Send to QRadar
            endpoint = f"{self._base_url}/siem/events"

            payload: dict[str, Any] = {
                "events": [
                    {
                        "device_time": datetime.utcnow().isoformat(),
                        "logsource_id": log_source_id or 116,
                        "sourceip": leef_event.source_ip or "0.0.0.0",
                        "severity": leef_event.severity,
                        "qid": 5013001,  # Generic event ID
                        "content": leef_string,
                    }
                ]
            }

            response = await self._client.post(endpoint, json=payload, timeout=self.config.timeout)

            if response.status_code in (200, 201, 202):
                logger.debug(f"Event sent to QRadar: {leef_event.name}")
                return True
            else:
                logger.error(f"Failed to send event: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"Error sending event to QRadar: {e}")
            return False

    async def send_batch(
        self, events: list[LEEFEvent | dict[str, Any]], batch_size: int = 100
    ) -> dict[str, int]:
        """
        Send multiple events to QRadar in batches.

        Args:
            events: List of events to send
            batch_size: Number of events per batch

        Returns:
            Dict with success and failed counts
        """
        results = {"success": 0, "failed": 0}

        for i in range(0, len(events), batch_size):
            batch = events[i : i + batch_size]

            for event in batch:
                success = await self.send_event(event)
                if success:
                    results["success"] += 1
                else:
                    results["failed"] += 1

            # Small delay between batches
            if i + batch_size < len(events):
                await asyncio.sleep(0.1)

        return results

    async def create_offense(
        self,
        title: str,
        description: str,
        severity: int = 5,
        source_ip: str | None = None,
        username: str | None = None,
        offense_type: str = "sourceip",
    ) -> int | None:
        """
        Create a new offense in QRadar.

        Args:
            title: Offense title
            description: Offense description
            severity: Severity level (1-10)
            source_ip: Source IP address
            username: Username if applicable
            offense_type: Type of offense

        Returns:
            Offense ID if successful, None otherwise
        """
        if not self._client:
            raise RuntimeError("QRadar client not connected")

        try:
            payload = {
                "name": title,
                "description": description,
                "severity": severity,
                "offense_type": self.config.offense_types.get(
                    offense_type, self.config.offense_types["sourceip"]
                ),
            }

            if source_ip:
                payload["source_ip"] = source_ip
            if username:
                payload["username"] = username

            response = await self._client.post(
                f"{self._base_url}/siem/offenses", json=payload, timeout=self.config.timeout
            )

            if response.status_code in (200, 201, 202):
                offense = response.json()
                offense_id = offense.get("id")
                logger.info(f"Created offense: {offense_id}")
                return offense_id
            else:
                logger.error(f"Failed to create offense: {response.text}")
                return None

        except Exception as e:
            logger.error(f"Error creating offense: {e}")
            return None

    async def get_offenses(
        self, status: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Get offenses from QRadar."""
        if not self._client:
            raise RuntimeError("QRadar client not connected")

        try:
            params = {"filter": "status != 'CLOSED'", "limit": limit}
            if status:
                params["filter"] = f"status = '{status}'"

            response = await self._client.get(
                f"{self._base_url}/siem/offenses", params=params, timeout=self.config.timeout
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get offenses: {response.text}")
                return []

        except Exception as e:
            logger.error(f"Error getting offenses: {e}")
            return []

    async def add_note(
        self, offense_id: int, note_text: str, username: str = "AI-Log-Filter"
    ) -> bool:
        """Add a note to an offense."""
        if not self._client:
            raise RuntimeError("QRadar client not connected")

        try:
            payload = {
                "note_text": note_text,
                "username": username,
            }

            response = await self._client.post(
                f"{self._base_url}/siem/offenses/{offense_id}/notes",
                json=payload,
                timeout=self.config.timeout,
            )

            return response.status_code in (200, 201, 202)

        except Exception as e:
            logger.error(f"Error adding note: {e}")
            return False

    async def run_ariel_query(
        self,
        query: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """
        Run an Ariel search query.

        Args:
            query: AQL query string
            start_time: Query start time
            end_time: Query end time
            timeout: Query timeout in seconds

        Returns:
            Query results
        """
        if not self._client:
            raise RuntimeError("QRadar client not connected")

        try:
            search_payload = {
                "query": query,
                "return": self.config.max_results,
            }

            if start_time:
                search_payload["startTime"] = start_time.isoformat()
            if end_time:
                search_payload["endTime"] = end_time.isoformat()

            # Create search
            response = await self._client.post(
                f"{self._base_url}/ariel/searches",
                json=search_payload,
                timeout=timeout or self.config.default_timeout,
            )

            if response.status_code != 202:
                return {"error": f"Search creation failed: {response.text}"}

            search_id = response.json().get("search_id")

            # Poll for results
            result = await self._wait_for_search(search_id, timeout)
            return result

        except Exception as e:
            logger.error(f"Error running Ariel query: {e}")
            return {"error": str(e)}

    async def _wait_for_search(self, search_id: str, timeout: int) -> dict[str, Any]:
        """Wait for Ariel search to complete."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            response = await self._client.get(
                f"{self._base_url}/ariel/searches/{search_id}", timeout=30.0
            )

            if response.status_code != 200:
                return {"error": f"Search status failed: {response.text}"}

            status = response.json()

            if status.get("status") == "COMPLETED":
                # Get results
                results_response = await self._client.get(
                    f"{self._base_url}/ariel/searches/{search_id}/results", timeout=timeout
                )
                return results_response.json()

            elif status.get("status") == "FAILED":
                return {"error": status.get("error", "Search failed")}

            await asyncio.sleep(2)

        return {"error": "Search timeout"}

    async def health_check(self) -> HealthStatus:
        """Check QRadar connection health."""
        start_time = time.time()

        try:
            response = await self._client.get(f"{self._base_url}/system/info", timeout=30.0)

            latency_ms = (time.time() - start_time) * 1000

            if response.status_code == 200:
                info = response.json()
                return HealthStatus(
                    healthy=True,
                    latency_ms=latency_ms,
                    message=f"QRadar {info.get('version', 'unknown')} connected",
                    details={"version": info.get("version"), "hostname": info.get("hostname")},
                )
            else:
                return HealthStatus(
                    healthy=False,
                    latency_ms=latency_ms,
                    message=f"QRadar returned {response.status_code}",
                    details={"status_code": response.status_code},
                )

        except Exception as e:
            return HealthStatus(
                healthy=False,
                latency_ms=0,
                message=f"QRadar health check failed: {e}",
                details={"error": str(e)},
            )

    async def is_healthy(self) -> bool:
        """Quick health check."""
        try:
            response = await self._client.get(f"{self._base_url}/system/info", timeout=10.0)
            return response.status_code == 200
        except Exception:
            return False


# Convenience function to create QRadar event from classification result
def create_qradar_event(
    log_message: str,
    category: str,
    confidence: float,
    source_ip: str | None = None,
    hostname: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> LEEFEvent:
    """Create a LEEF event from classification result."""

    # Map category to severity
    severity_map = {
        "critical": 10,
        "suspicious": 7,
        "routine": 3,
        "noise": 1,
    }

    severity = severity_map.get(category.lower(), 5)

    return LEEFEvent(
        name=f"AI-Classified: {category.upper()}",
        severity=severity,
        source_ip=source_ip,
        source_host=hostname,
        message_id=str(uuid.uuid4()),
        extensions={
            "ai_category": category,
            "ai_confidence": f"{confidence:.2f}",
            "ai_raw_message": log_message[:500],  # Limit message length
            **(metadata or {}),
        },
    )
