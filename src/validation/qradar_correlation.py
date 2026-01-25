"""
QRadar Offense Correlation

Correlates AI classification decisions with QRadar offense generation
to detect false negatives (logs that the AI filtered but should have
been sent to QRadar).

This is critical for:
1. Shadow mode validation
2. Continuous model quality monitoring
3. Identifying gaps in detection coverage
"""

import asyncio
import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import httpx

from src.monitoring.production_metrics import FALSE_NEGATIVES_TOTAL
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ClassificationRecord:
    """Record of an AI classification decision."""
    log_id: str
    timestamp: datetime
    message_hash: str
    source_ip: str | None
    source: str
    category: str
    confidence: float
    message_preview: str


@dataclass
class QRadarOffense:
    """QRadar offense data."""
    offense_id: int
    description: str
    offense_type: int
    offense_type_name: str
    severity: int
    status: str
    source_ips: list[str]
    log_sources: list[str]
    start_time: datetime
    last_updated: datetime
    event_count: int
    categories: list[str]


@dataclass
class CorrelationMatch:
    """A match between an AI decision and a QRadar offense."""
    classification_record: ClassificationRecord
    offense: QRadarOffense
    correlation_type: str  # 'ip_match', 'message_match', 'source_match', 'time_window'
    confidence: float
    is_false_negative: bool


class QRadarClient:
    """Client for QRadar API interactions."""

    def __init__(self, config: dict[str, Any]):
        self.host = config.get("host", "localhost")
        self.port = config.get("port", 443)
        self.token = config.get("token")
        self.verify_ssl = config.get("verify_ssl", True)
        self.timeout = config.get("timeout", 30)
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=f"https://{self.host}:{self.port}/api",
                verify=self.verify_ssl,
                timeout=self.timeout,
                headers={
                    "SEC": self.token,
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                }
            )
        return self._client

    async def get_offenses(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        status: str = "OPEN",
        limit: int = 100
    ) -> list[QRadarOffense]:
        """Fetch offenses from QRadar."""
        client = await self._get_client()

        # Build filter
        filters = []
        if status:
            filters.append(f"status = '{status}'")
        if start_time:
            epoch_ms = int(start_time.timestamp() * 1000)
            filters.append(f"start_time >= {epoch_ms}")
        if end_time:
            epoch_ms = int(end_time.timestamp() * 1000)
            filters.append(f"start_time <= {epoch_ms}")

        filter_str = " AND ".join(filters) if filters else ""

        params = {
            "filter": filter_str,
            "Range": f"items=0-{limit-1}"
        }

        try:
            response = await client.get("/siem/offenses", params=params)
            response.raise_for_status()
            offenses_data = response.json()

            offenses = []
            for data in offenses_data:
                offense = QRadarOffense(
                    offense_id=data["id"],
                    description=data.get("description", ""),
                    offense_type=data.get("offense_type", 0),
                    offense_type_name=data.get("offense_type_name", "Unknown"),
                    severity=data.get("severity", 0),
                    status=data.get("status", "UNKNOWN"),
                    source_ips=data.get("source_network", {}).get("source_ips", []),
                    log_sources=data.get("log_sources", []),
                    start_time=datetime.fromtimestamp(data["start_time"] / 1000),
                    last_updated=datetime.fromtimestamp(data["last_updated_time"] / 1000),
                    event_count=data.get("event_count", 0),
                    categories=data.get("categories", [])
                )
                offenses.append(offense)

            logger.debug(f"Fetched {len(offenses)} offenses from QRadar")
            return offenses

        except httpx.HTTPStatusError as e:
            logger.error(f"QRadar API error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Failed to fetch offenses: {e}")
            raise

    async def get_offense_events(
        self,
        offense_id: int,
        limit: int = 100
    ) -> list[dict[str, Any]]:
        """Get events associated with an offense."""
        client = await self._get_client()

        # AQL query to get events for offense
        aql = f"""
        SELECT * FROM events
        WHERE INOFFENSE({offense_id})
        LIMIT {limit}
        LAST 24 HOURS
        """

        try:
            # Start search
            response = await client.post(
                "/ariel/searches",
                json={"query_expression": aql}
            )
            response.raise_for_status()
            search_id = response.json()["search_id"]

            # Wait for results
            for _ in range(30):  # Max 30 seconds
                await asyncio.sleep(1)
                status_response = await client.get(f"/ariel/searches/{search_id}")
                status_response.raise_for_status()
                status_data = status_response.json()

                if status_data["status"] == "COMPLETED":
                    break

            # Get results
            results_response = await client.get(f"/ariel/searches/{search_id}/results")
            results_response.raise_for_status()

            return results_response.json().get("events", [])

        except Exception as e:
            logger.error(f"Failed to get offense events: {e}")
            return []

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


class OffenseCorrelator:
    """
    Correlates AI classifications with QRadar offenses to detect false negatives.

    This is the core component for:
    1. Shadow mode validation - comparing AI decisions vs actual offenses
    2. Continuous monitoring - detecting when AI misses threats in production
    3. Model improvement - identifying patterns that need better coverage

    Correlation strategies:
    - IP matching: Same source IP in classification and offense
    - Time window: Events within N minutes of offense start
    - Message similarity: Similar log patterns
    - Log source matching: Same log source
    """

    def __init__(
        self,
        qradar_config: dict[str, Any],
        correlation_config: dict[str, Any] | None = None
    ):
        self.qradar = QRadarClient(qradar_config)
        self.config = correlation_config or {}

        # Correlation settings
        self.time_window_minutes = self.config.get("time_window_minutes", 60)
        self.ip_match_weight = self.config.get("ip_match_weight", 0.4)
        self.time_match_weight = self.config.get("time_match_weight", 0.3)
        self.source_match_weight = self.config.get("source_match_weight", 0.3)
        self.min_correlation_confidence = self.config.get("min_correlation_confidence", 0.6)

        # Storage for classification records
        self.classifications: dict[str, ClassificationRecord] = {}
        self.classifications_by_ip: dict[str, list[str]] = defaultdict(list)
        self.classifications_by_source: dict[str, list[str]] = defaultdict(list)

        # Results
        self.matches: list[CorrelationMatch] = []
        self.false_negatives: list[CorrelationMatch] = []

        # Stats
        self.stats = {
            "total_classifications": 0,
            "total_offenses_checked": 0,
            "total_correlations": 0,
            "false_negatives_detected": 0,
            "by_offense_type": defaultdict(int),
            "by_original_category": defaultdict(int)
        }

        logger.info("OffenseCorrelator initialized")

    def record_classification(
        self,
        log_id: str,
        message: str,
        source: str,
        category: str,
        confidence: float,
        source_ip: str | None = None,
        timestamp: datetime | None = None
    ):
        """Record an AI classification for later correlation."""
        record = ClassificationRecord(
            log_id=log_id,
            timestamp=timestamp or datetime.utcnow(),
            message_hash=hashlib.md5(message.encode()).hexdigest(),
            source_ip=source_ip,
            source=source,
            category=category,
            confidence=confidence,
            message_preview=message[:200]
        )

        self.classifications[log_id] = record
        self.stats["total_classifications"] += 1

        # Index by IP for fast lookup
        if source_ip:
            self.classifications_by_ip[source_ip].append(log_id)

        # Index by source
        self.classifications_by_source[source].append(log_id)

        # Cleanup old records (keep last 24 hours)
        self._cleanup_old_records()

    def _cleanup_old_records(self, max_age_hours: int = 24):
        """Remove classification records older than max_age_hours."""
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)

        to_remove = [
            log_id for log_id, record in self.classifications.items()
            if record.timestamp < cutoff
        ]

        for log_id in to_remove:
            record = self.classifications.pop(log_id)
            if record.source_ip and log_id in self.classifications_by_ip[record.source_ip]:
                self.classifications_by_ip[record.source_ip].remove(log_id)
            if log_id in self.classifications_by_source[record.source]:
                self.classifications_by_source[record.source].remove(log_id)

    async def correlate_with_offenses(
        self,
        lookback_hours: int = 1
    ) -> list[CorrelationMatch]:
        """
        Fetch recent offenses and correlate with stored classifications.

        Returns list of matches, highlighting false negatives.
        """
        start_time = datetime.utcnow() - timedelta(hours=lookback_hours)

        try:
            offenses = await self.qradar.get_offenses(
                start_time=start_time,
                status="OPEN",
                limit=100
            )
        except Exception as e:
            logger.error(f"Failed to fetch offenses for correlation: {e}")
            return []

        self.stats["total_offenses_checked"] += len(offenses)
        new_matches = []

        for offense in offenses:
            matches = self._find_correlations(offense)

            for match in matches:
                self.stats["total_correlations"] += 1

                if match.is_false_negative:
                    self.stats["false_negatives_detected"] += 1
                    self.stats["by_offense_type"][offense.offense_type_name] += 1
                    self.stats["by_original_category"][match.classification_record.category] += 1

                    self.false_negatives.append(match)

                    # Record in metrics
                    FALSE_NEGATIVES_TOTAL.labels(
                        original_category=match.classification_record.category,
                        offense_type=offense.offense_type_name,
                        severity=str(offense.severity)
                    ).inc()

                    # Log the false negative
                    logger.error(
                        "FALSE NEGATIVE DETECTED",
                        extra={
                            "log_id": match.classification_record.log_id,
                            "original_category": match.classification_record.category,
                            "original_confidence": match.classification_record.confidence,
                            "offense_id": offense.offense_id,
                            "offense_type": offense.offense_type_name,
                            "offense_severity": offense.severity,
                            "correlation_type": match.correlation_type,
                            "correlation_confidence": match.confidence
                        }
                    )

                new_matches.append(match)

        self.matches.extend(new_matches)
        return new_matches

    def _find_correlations(self, offense: QRadarOffense) -> list[CorrelationMatch]:
        """Find classification records that correlate with an offense."""
        matches = []
        checked_log_ids = set()

        time_window_start = offense.start_time - timedelta(minutes=self.time_window_minutes)
        time_window_end = offense.start_time + timedelta(minutes=5)  # Small buffer

        # Strategy 1: IP matching
        for source_ip in offense.source_ips:
            for log_id in self.classifications_by_ip.get(source_ip, []):
                if log_id in checked_log_ids:
                    continue
                checked_log_ids.add(log_id)

                record = self.classifications[log_id]

                # Check time window
                if not (time_window_start <= record.timestamp <= time_window_end):
                    continue

                # Calculate correlation confidence
                confidence = self._calculate_correlation_confidence(
                    record, offense, "ip_match"
                )

                if confidence >= self.min_correlation_confidence:
                    is_false_negative = record.category in ["routine", "noise"]
                    matches.append(CorrelationMatch(
                        classification_record=record,
                        offense=offense,
                        correlation_type="ip_match",
                        confidence=confidence,
                        is_false_negative=is_false_negative
                    ))

        # Strategy 2: Log source matching
        for log_source in offense.log_sources:
            # Normalize log source name
            normalized = log_source.lower().replace(" ", "_")

            for source, log_ids in self.classifications_by_source.items():
                if normalized in source.lower() or source.lower() in normalized:
                    for log_id in log_ids:
                        if log_id in checked_log_ids:
                            continue
                        checked_log_ids.add(log_id)

                        record = self.classifications[log_id]

                        # Check time window
                        if not (time_window_start <= record.timestamp <= time_window_end):
                            continue

                        confidence = self._calculate_correlation_confidence(
                            record, offense, "source_match"
                        )

                        if confidence >= self.min_correlation_confidence:
                            is_false_negative = record.category in ["routine", "noise"]
                            matches.append(CorrelationMatch(
                                classification_record=record,
                                offense=offense,
                                correlation_type="source_match",
                                confidence=confidence,
                                is_false_negative=is_false_negative
                            ))

        # Strategy 3: Time window for unchecked high-severity offenses
        if offense.severity >= 7:  # High severity
            for log_id, record in self.classifications.items():
                if log_id in checked_log_ids:
                    continue

                if time_window_start <= record.timestamp <= time_window_end:
                    # For high-severity offenses, flag anything in time window
                    # that was classified as routine/noise
                    if record.category in ["routine", "noise"]:
                        confidence = 0.5  # Lower confidence for time-only match

                        if confidence >= self.min_correlation_confidence:
                            matches.append(CorrelationMatch(
                                classification_record=record,
                                offense=offense,
                                correlation_type="time_window",
                                confidence=confidence,
                                is_false_negative=True
                            ))

        return matches

    def _calculate_correlation_confidence(
        self,
        record: ClassificationRecord,
        offense: QRadarOffense,
        correlation_type: str
    ) -> float:
        """Calculate confidence score for a correlation."""
        confidence = 0.0

        # Base confidence by correlation type
        if correlation_type == "ip_match":
            confidence += self.ip_match_weight
        elif correlation_type == "source_match":
            confidence += self.source_match_weight

        # Time proximity bonus
        time_diff = abs((offense.start_time - record.timestamp).total_seconds())
        if time_diff < 60:  # Within 1 minute
            confidence += self.time_match_weight
        elif time_diff < 300:  # Within 5 minutes
            confidence += self.time_match_weight * 0.7
        elif time_diff < 900:  # Within 15 minutes
            confidence += self.time_match_weight * 0.4

        # Severity bonus - higher severity offenses are more likely matches
        severity_bonus = (offense.severity / 10) * 0.2
        confidence += severity_bonus

        return min(confidence, 1.0)

    def get_false_negative_report(self) -> dict[str, Any]:
        """Generate a report of detected false negatives."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "summary": {
                "total_classifications_tracked": self.stats["total_classifications"],
                "total_offenses_checked": self.stats["total_offenses_checked"],
                "total_correlations": self.stats["total_correlations"],
                "false_negatives_detected": self.stats["false_negatives_detected"],
                "false_negative_rate": (
                    self.stats["false_negatives_detected"] /
                    max(self.stats["total_classifications"], 1)
                )
            },
            "by_offense_type": dict(self.stats["by_offense_type"]),
            "by_original_category": dict(self.stats["by_original_category"]),
            "recent_false_negatives": [
                {
                    "log_id": fn.classification_record.log_id,
                    "timestamp": fn.classification_record.timestamp.isoformat(),
                    "original_category": fn.classification_record.category,
                    "original_confidence": fn.classification_record.confidence,
                    "message_preview": fn.classification_record.message_preview,
                    "offense_id": fn.offense.offense_id,
                    "offense_type": fn.offense.offense_type_name,
                    "offense_severity": fn.offense.severity,
                    "correlation_type": fn.correlation_type,
                    "correlation_confidence": fn.confidence
                }
                for fn in self.false_negatives[-20:]  # Last 20
            ]
        }

    async def run_continuous_correlation(
        self,
        interval_seconds: int = 300,
        callback: callable | None = None
    ):
        """
        Run continuous correlation in the background.

        Args:
            interval_seconds: How often to check for new offenses
            callback: Optional function to call when false negatives are found
        """
        logger.info(f"Starting continuous correlation every {interval_seconds}s")

        while True:
            try:
                matches = await self.correlate_with_offenses(lookback_hours=1)

                false_negatives = [m for m in matches if m.is_false_negative]

                if false_negatives and callback:
                    await callback(false_negatives)

                logger.info(
                    f"Correlation run complete: {len(matches)} correlations, "
                    f"{len(false_negatives)} false negatives"
                )

            except Exception as e:
                logger.error(f"Error in continuous correlation: {e}")

            await asyncio.sleep(interval_seconds)

    async def close(self):
        """Cleanup resources."""
        await self.qradar.close()


# Factory function
def create_correlator(
    qradar_config: dict[str, Any],
    correlation_config: dict[str, Any] | None = None
) -> OffenseCorrelator:
    """Create an offense correlator instance."""
    return OffenseCorrelator(qradar_config, correlation_config)


# Integration helper for shadow mode
class ShadowModeCorrelationIntegration:
    """
    Integrates offense correlation with shadow mode validation.

    This class bridges the gap between the AI classifier's shadow mode
    and QRadar offense detection to automatically validate classifications.
    """

    def __init__(
        self,
        correlator: OffenseCorrelator,
        shadow_validator: Any  # ShadowModeValidator
    ):
        self.correlator = correlator
        self.validator = shadow_validator

    async def process_classification(
        self,
        log_id: str,
        log: dict[str, Any],
        prediction: Any  # Prediction
    ):
        """Process a classification and record for correlation."""
        # Extract source IP from log if present
        source_ip = self._extract_ip(log.get("message", ""))

        # Record in correlator
        self.correlator.record_classification(
            log_id=log_id,
            message=log.get("message", ""),
            source=log.get("source", "unknown"),
            category=prediction.category,
            confidence=prediction.confidence,
            source_ip=source_ip
        )

        # Record in shadow validator
        await self.validator.record_decision(log_id, prediction, log)

    def _extract_ip(self, message: str) -> str | None:
        """Extract first IP address from message."""
        ip_pattern = r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b"
        match = re.search(ip_pattern, message)
        return match.group(1) if match else None

    async def sync_with_qradar(self):
        """Sync correlation results with shadow validator."""
        matches = await self.correlator.correlate_with_offenses()

        for match in matches:
            offense_data = {
                "offense_id": str(match.offense.offense_id),
                "offense_type": match.offense.offense_type_name,
                "severity": match.offense.severity
            }

            await self.validator.record_qradar_result(
                log_id=match.classification_record.log_id,
                offense_generated=True,
                offense_data=offense_data
            )
