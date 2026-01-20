"""
Unit tests for log parser
"""

import pytest

from src.preprocessing.log_parser import FeatureExtractor, LogParser


class TestLogParser:
    """Tests for LogParser class."""

    @pytest.fixture
    def parser(self):
        return LogParser()

    def test_parse_syslog_rfc3164(self, parser):
        """Test parsing BSD syslog format."""
        log = "Jan  5 12:34:56 myhost sshd[1234]: Failed password for user admin"
        result = parser.parse(log)

        assert result["format"] == "syslog_rfc3164"
        assert result["hostname"] == "myhost"
        assert result["process"] == "sshd"
        assert "Failed password" in result["message"]

    def test_parse_json_log(self, parser):
        """Test parsing JSON format."""
        log = '{"timestamp": "2024-01-05T12:34:56Z", "level": "ERROR", "message": "Connection failed"}'
        result = parser.parse(log)

        assert result["format"] == "json"
        assert result["level"] == "ERROR"
        assert result["message"] == "Connection failed"

    def test_parse_leef_format(self, parser):
        """Test parsing LEEF format (QRadar)."""
        log = "LEEF:2.0|IBM|QRadar|1.0|LoginFailed|src=192.168.1.1\tmsg=Authentication failed"
        result = parser.parse(log)

        assert result["format"] == "leef"
        assert result["vendor"] == "IBM"
        assert result["product"] == "QRadar"

    def test_parse_cef_format(self, parser):
        """Test parsing CEF format."""
        log = "CEF:0|Security|IDS|1.0|100|Intrusion Detected|10|src=192.168.1.1"
        result = parser.parse(log)

        assert result["format"] == "cef"
        assert result["vendor"] == "Security"
        assert result["severity"] == "10"

    def test_parse_generic_log(self, parser):
        """Test parsing generic text log."""
        log = "2024-01-05 12:34:56 ERROR: Something went wrong"
        result = parser.parse(log)

        assert result["format"] == "generic"
        assert "ERROR" in result["message"]

    def test_parse_empty_log(self, parser):
        """Test parsing empty log."""
        result = parser.parse("")

        assert result["format"] == "empty"
        assert result["message"] == ""

    def test_extract_ip_addresses(self, parser):
        """Test IP address extraction."""
        log = "Connection from 192.168.1.100 to 10.0.0.1"
        result = parser.parse(log)

        assert "ip_addresses" in result
        assert "192.168.1.100" in result["ip_addresses"]
        assert "10.0.0.1" in result["ip_addresses"]


class TestFeatureExtractor:
    """Tests for FeatureExtractor class."""

    @pytest.fixture
    def extractor(self):
        return FeatureExtractor()

    def test_extract_basic_features(self, extractor):
        """Test basic feature extraction."""
        parsed = {
            # Use "login" keyword which matches the has_auth regex pattern
            "message": "ERROR: Login authentication failed for user admin",
            "format": "generic"
        }

        features = extractor.extract(parsed)

        assert features["message_length"] > 0
        assert features["word_count"] == 7
        assert features["has_error"] is True
        # "login" matches the auth pattern: \b(auth|login|password|credential)\b
        assert features["has_auth"] is True

    def test_preprocess_text_normalizes_ips(self, extractor):
        """Test that IPs are normalized."""
        text = "Connection from 192.168.1.1 to 10.0.0.1"
        result = extractor.preprocess_text(text)

        # The preprocess_text method lowercases the output
        assert "<ip>" in result
        assert "192.168.1.1" not in result

    def test_preprocess_text_normalizes_timestamps(self, extractor):
        """Test that timestamps are normalized."""
        text = "Event at 2024-01-05T12:34:56Z"
        result = extractor.preprocess_text(text)

        # The preprocess_text method lowercases the output
        assert "<timestamp>" in result
        assert "2024-01-05" not in result

    def test_preprocess_text_normalizes_paths(self, extractor):
        """Test that file paths are normalized."""
        text = "Accessing file /var/log/syslog"
        result = extractor.preprocess_text(text)

        # The preprocess_text method lowercases the output
        assert "<path>" in result
        assert "/var/log" not in result
