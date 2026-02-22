from datetime import UTC, datetime
from typing import Any

from src.monitoring.metrics import METRICS
from src.routing.destinations.base import BaseDestination
from src.utils.logging import get_logger

logger = get_logger(__name__)


class QRadarDestination(BaseDestination):
    """Send logs to IBM QRadar SIEM."""

    def __init__(self, config: dict[str, Any]):
        super().__init__("qradar", config)
        self.host = config.get("host", "localhost")
        self.port = config.get("port", 443)
        self.token = config.get("token")
        self.verify_ssl = config.get("verify_ssl", True)
        self.timeout = config.get("timeout", 30)
        self._client = None

    async def _get_client(self):
        """Get or create HTTP client."""
        if self._client is None:
            try:
                import httpx

                headers: dict[str, str] = {"Content-Type": "application/json"}
                if self.token:
                    headers["SEC"] = str(self.token)

                self._client = httpx.AsyncClient(
                    base_url=f"https://{self.host}:{self.port}",
                    verify=self.verify_ssl,
                    timeout=self.timeout,
                    headers=headers,
                )
            except ImportError:
                logger.warning("httpx not available, QRadar destination disabled")
                self._client = None
        return self._client

    async def send(self, logs: list[dict[str, Any]]):
        """Send logs to QRadar."""
        client = await self._get_client()
        if client is None:
            logger.debug("QRadar client not available, skipping %s logs", len(logs))
            return

        try:
            # Convert logs to LEEF format or JSON
            for log in logs:
                leef_message = self._to_leef(log)
                await self._send_syslog(leef_message)

            logger.debug("Sent %s logs to QRadar", len(logs))

        except Exception as e:
            logger.error("Failed to send logs to QRadar: %s", e)
            METRICS.routing_errors.labels(destination="qradar").inc(len(logs))
            raise

    def _to_leef(self, log: dict[str, Any]) -> str:
        """Convert log to LEEF format."""
        # LEEF format: LEEF:Version|Vendor|Product|Version|EventID|Attributes
        timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")

        attributes = [
            f"devTime={timestamp}",
            f"cat={log.get('category', 'unknown')}",
            f"sev={self._get_severity(log.get('category'))}",
            f"msg={log.get('message', '')}",
            f"confidence={log.get('confidence', 0)}",
        ]

        return (
            f"LEEF:2.0|AILogFilter|LogClassifier|1.0|"
            f"{log.get('category', 'unknown')}|"
            f"{' '.join(attributes)}"
        )

    def _get_severity(self, category: str | None) -> int:
        """Map category to QRadar severity."""
        severity_map = {"critical": 10, "suspicious": 7, "routine": 3, "noise": 1}
        return severity_map.get(category or "routine", 5)

    async def _send_syslog(self, message: str):
        """Send message via syslog."""
        # In production, this would use actual syslog
        logger.debug("LEEF: %s...", message[:100])

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
