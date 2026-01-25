"""
Log Parser - Parse various log formats into structured data

Supports:
- LEEF (Log Event Extended Format) - IBM QRadar
- CEF (Common Event Format)
- Syslog
- JSON
- Generic text logs
"""

import json
import re
from dataclasses import dataclass
from typing import Any

from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class LogFormat:
    """Definition of a log format."""

    name: str
    pattern: str
    parser: callable


class LogParser:
    """
    Multi-format log parser.

    Automatically detects and parses logs in various formats including
    LEEF, CEF, Syslog, JSON, and generic text formats.
    """

    def __init__(self):
        self.formats = self._initialize_formats()

    def _initialize_formats(self) -> list[tuple[str, re.Pattern, callable]]:
        """Initialize supported log formats."""
        return [
            ("leef", re.compile(
                r"LEEF:(?P<version>[^|]+)\|(?P<vendor>[^|]+)\|"
                r"(?P<product>[^|]+)\|(?P<prod_version>[^|]+)\|"
                r"(?P<event_id>[^|]+)\|(?P<attributes>.*)"
            ), self._parse_leef),

            ("cef", re.compile(
                r"CEF:(?P<version>\d+)\|(?P<vendor>[^|]+)\|"
                r"(?P<product>[^|]+)\|(?P<prod_version>[^|]+)\|"
                r"(?P<signature_id>[^|]+)\|(?P<name>[^|]+)\|"
                r"(?P<severity>[^|]+)\|(?P<extension>.*)"
            ), self._parse_cef),

            ("syslog_rfc5424", re.compile(
                r"^<(?P<priority>\d+)>(?P<version>\d+)\s+"
                r"(?P<timestamp>\S+)\s+(?P<hostname>\S+)\s+"
                r"(?P<app_name>\S+)\s+(?P<proc_id>\S+)\s+"
                r"(?P<msg_id>\S+)\s+(?P<structured_data>\[.*?\]|-)\s*"
                r"(?P<message>.*)"
            ), self._parse_syslog_rfc5424),

            ("syslog_rfc3164", re.compile(
                r"^(?:<(?P<priority>\d+)>)?(?P<timestamp>\w{3}\s+\d{1,2}\s+"
                r"\d{2}:\d{2}:\d{2})\s+(?P<hostname>\S+)\s+"
                r"(?P<process>\S+?)(?:\[(?P<pid>\d+)\])?:\s+(?P<message>.*)"
            ), self._parse_syslog_rfc3164),

            ("json", re.compile(r"^\s*\{.*\}\s*$", re.DOTALL), self._parse_json),
        ]

    def parse(self, log_message: str) -> dict[str, Any]:
        """
        Parse a log message into structured format.

        Args:
            log_message: Raw log message string

        Returns:
            Dictionary with parsed fields
        """
        if not log_message or not log_message.strip():
            return {"raw": log_message, "format": "empty", "message": ""}

        log_message = log_message.strip()

        # Try each format
        for format_name, pattern, parser in self.formats:
            match = pattern.match(log_message)
            if match:
                try:
                    parsed = parser(match)
                    parsed["format"] = format_name
                    parsed["raw"] = log_message
                    return parsed
                except Exception as e:
                    logger.debug(f"Failed to parse as {format_name}: {e}")
                    continue

        # Default: treat as generic text
        return self._parse_generic(log_message)

    def _parse_leef(self, match: re.Match) -> dict[str, Any]:
        """Parse LEEF format (IBM QRadar)."""
        result = {
            "leef_version": match.group("version"),
            "vendor": match.group("vendor"),
            "product": match.group("product"),
            "product_version": match.group("prod_version"),
            "event_id": match.group("event_id"),
        }

        # Parse attributes (key=value pairs, tab or space separated)
        attributes = match.group("attributes")
        if attributes:
            result["attributes"] = self._parse_key_value_pairs(attributes)
            # Extract message from attributes if present
            if "msg" in result["attributes"]:
                result["message"] = result["attributes"]["msg"]
            elif "cat" in result["attributes"]:
                result["message"] = result["attributes"]["cat"]
            else:
                result["message"] = attributes
        else:
            result["message"] = match.group("event_id")

        return result

    def _parse_cef(self, match: re.Match) -> dict[str, Any]:
        """Parse CEF format."""
        result = {
            "cef_version": match.group("version"),
            "vendor": match.group("vendor"),
            "product": match.group("product"),
            "product_version": match.group("prod_version"),
            "signature_id": match.group("signature_id"),
            "name": match.group("name"),
            "severity": match.group("severity"),
            "message": match.group("name"),
        }

        # Parse extension
        extension = match.group("extension")
        if extension:
            result["extension"] = self._parse_key_value_pairs(extension)
            if "msg" in result["extension"]:
                result["message"] = result["extension"]["msg"]

        return result

    def _parse_syslog_rfc5424(self, match: re.Match) -> dict[str, Any]:
        """Parse RFC 5424 syslog format."""
        priority = int(match.group("priority"))
        facility = priority // 8
        severity = priority % 8

        return {
            "priority": priority,
            "facility": facility,
            "severity": severity,
            "version": match.group("version"),
            "timestamp": match.group("timestamp"),
            "hostname": match.group("hostname"),
            "app_name": match.group("app_name"),
            "proc_id": match.group("proc_id"),
            "msg_id": match.group("msg_id"),
            "structured_data": match.group("structured_data"),
            "message": match.group("message"),
        }

    def _parse_syslog_rfc3164(self, match: re.Match) -> dict[str, Any]:
        """Parse RFC 3164 (BSD) syslog format."""
        result = {
            "timestamp": match.group("timestamp"),
            "hostname": match.group("hostname"),
            "process": match.group("process"),
            "message": match.group("message"),
        }

        if match.group("priority"):
            priority = int(match.group("priority"))
            result["priority"] = priority
            result["facility"] = priority // 8
            result["severity"] = priority % 8

        if match.group("pid"):
            result["pid"] = match.group("pid")

        return result

    def _parse_json(self, match: re.Match) -> dict[str, Any]:
        """Parse JSON log format."""
        data = json.loads(match.group(0))

        # Extract message from common fields
        message_fields = ["message", "msg", "log", "text", "event", "@message"]
        for field in message_fields:
            if field in data:
                data["message"] = str(data[field])
                break
        else:
            # Use entire JSON as message
            data["message"] = match.group(0)

        return data

    def _parse_generic(self, log_message: str) -> dict[str, Any]:
        """Parse generic text log."""
        result = {
            "format": "generic",
            "raw": log_message,
            "message": log_message,
        }

        # Try to extract common fields
        # Timestamp patterns
        timestamp_patterns = [
            (r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)", "timestamp"),
            (r"(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})", "timestamp"),
        ]

        for pattern, field in timestamp_patterns:
            match = re.search(pattern, log_message)
            if match:
                result[field] = match.group(1)
                break

        # IP addresses
        ip_pattern = r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b"
        ips = re.findall(ip_pattern, log_message)
        if ips:
            result["ip_addresses"] = ips
            if len(ips) >= 2:
                result["source_ip"] = ips[0]
                result["destination_ip"] = ips[1]
            elif len(ips) == 1:
                result["source_ip"] = ips[0]

        # Log level
        level_pattern = r"\b(DEBUG|INFO|WARN(?:ING)?|ERROR|CRITICAL|FATAL|TRACE)\b"
        level_match = re.search(level_pattern, log_message, re.IGNORECASE)
        if level_match:
            result["level"] = level_match.group(1).upper()

        return result

    def _parse_key_value_pairs(
        self,
        text: str,
        delimiter: str = r"[\t ]+"
    ) -> dict[str, str]:
        """Parse key=value pairs from text."""
        result = {}

        # Pattern for key=value (handling quoted values)
        kv_pattern = r'(\w+)=(?:"([^"]*?)"|([^\s]*))'

        for match in re.finditer(kv_pattern, text):
            key = match.group(1)
            value = match.group(2) if match.group(2) is not None else match.group(3)
            result[key] = value

        return result


class FeatureExtractor:
    """
    Extract features from parsed logs for ML models.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.max_length = self.config.get("max_message_length", 512)

    def extract(self, parsed_log: dict[str, Any]) -> dict[str, Any]:
        """
        Extract features from a parsed log.

        Args:
            parsed_log: Dictionary from LogParser

        Returns:
            Dictionary of extracted features
        """
        message = parsed_log.get("message", parsed_log.get("raw", ""))

        features = {
            # Text features
            "message": message[:self.max_length],
            "message_length": len(message),
            "word_count": len(message.split()),

            # Character-level features
            "digit_count": sum(c.isdigit() for c in message),
            "special_char_count": sum(not c.isalnum() and not c.isspace() for c in message),
            "uppercase_ratio": sum(c.isupper() for c in message) / max(len(message), 1),

            # Log metadata
            "log_format": parsed_log.get("format", "unknown"),
            "has_timestamp": "timestamp" in parsed_log,
            "has_ip": "source_ip" in parsed_log or "ip_addresses" in parsed_log,

            # Keyword indicators
            "has_error": bool(re.search(r"\b(error|fail|exception)\b", message, re.I)),
            "has_warning": bool(re.search(r"\b(warn|warning|alert)\b", message, re.I)),
            "has_auth": bool(re.search(r"\b(auth|login|password|credential)\b", message, re.I)),
            "has_network": bool(re.search(r"\b(connection|port|socket|tcp|udp)\b", message, re.I)),
        }

        # Add structured fields if available
        if "severity" in parsed_log:
            features["severity"] = parsed_log["severity"]
        if "facility" in parsed_log:
            features["facility"] = parsed_log["facility"]
        if "vendor" in parsed_log:
            features["vendor"] = parsed_log["vendor"]
        if "product" in parsed_log:
            features["product"] = parsed_log["product"]

        return features

    def preprocess_text(self, text: str) -> str:
        """
        Preprocess text for ML models.

        Normalizes various patterns to reduce vocabulary size while
        preserving semantic meaning.
        """
        # Normalize IP addresses
        text = re.sub(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "<IP>", text)

        # Normalize timestamps
        text = re.sub(
            r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?",
            "<TIMESTAMP>",
            text
        )

        # Normalize hex values
        text = re.sub(r"0x[0-9a-fA-F]+", "<HEX>", text)

        # Normalize UUIDs
        text = re.sub(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            "<UUID>",
            text,
            flags=re.IGNORECASE
        )

        # Normalize file paths
        text = re.sub(r"(/[\w\-./]+)+", "<PATH>", text)
        text = re.sub(r"([A-Za-z]:\\[\w\-\\./]+)+", "<PATH>", text)

        # Normalize email addresses
        text = re.sub(r"\b[\w.-]+@[\w.-]+\.\w+\b", "<EMAIL>", text)

        # Normalize URLs
        text = re.sub(r"https?://\S+", "<URL>", text)

        # Normalize large numbers
        text = re.sub(r"\b\d{5,}\b", "<LONGNUM>", text)

        # Lowercase
        text = text.lower()

        # Normalize whitespace
        text = re.sub(r"\s+", " ", text).strip()

        return text
