"""
Text Preprocessing Utilities

Shared text normalization for log classification models.
Reduces vocabulary size while preserving semantic meaning.
"""

import re

# Pre-compiled patterns for performance
_IP_PATTERN = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")
_TIMESTAMP_PATTERN = re.compile(
    r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?"
)
_HEX_PATTERN = re.compile(r"0x[0-9a-fA-F]+")
_UUID_PATTERN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)
_EMAIL_PATTERN = re.compile(r"\b[\w.%+-]+@[\w.-]+\.\w{2,}\b")
_MAC_PATTERN = re.compile(r"\b(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\b", re.IGNORECASE)
_HASH_MD5_PATTERN = re.compile(r"\b[a-f0-9]{32}\b", re.IGNORECASE)
_HASH_SHA1_PATTERN = re.compile(r"\b[a-f0-9]{40}\b", re.IGNORECASE)
_HASH_SHA256_PATTERN = re.compile(r"\b[a-f0-9]{64}\b", re.IGNORECASE)
_UNIX_PATH_PATTERN = re.compile(r"(/[\w\-./]+)+")
_WINDOWS_PATH_PATTERN = re.compile(r"([A-Za-z]:\\[\w\-\\./]+)+")
_URL_PATTERN = re.compile(r"https?://\S+")
_LONGNUM_PATTERN = re.compile(r"\b\d{5,}\b")
_WHITESPACE_PATTERN = re.compile(r"\s+")


def normalize_log_text(text: str) -> str:
    """
    Normalize log text by replacing variable tokens with placeholders.

    Replaces IPs, timestamps, UUIDs, emails, MACs, hashes, paths,
    URLs, and large numbers with consistent tokens. Lowercases and
    normalizes whitespace.

    Args:
        text: Raw log message text

    Returns:
        Normalized text suitable for ML classification
    """
    text = _IP_PATTERN.sub("<IP>", text)
    text = _TIMESTAMP_PATTERN.sub("<TIMESTAMP>", text)
    text = _HEX_PATTERN.sub("<HEX>", text)
    text = _UUID_PATTERN.sub("<UUID>", text)
    text = _EMAIL_PATTERN.sub("<EMAIL>", text)
    text = _MAC_PATTERN.sub("<MAC>", text)
    text = _HASH_SHA256_PATTERN.sub("<HASH>", text)
    text = _HASH_SHA1_PATTERN.sub("<HASH>", text)
    text = _HASH_MD5_PATTERN.sub("<HASH>", text)
    text = _UNIX_PATH_PATTERN.sub("<PATH>", text)
    text = _WINDOWS_PATH_PATTERN.sub("<PATH>", text)
    text = _URL_PATTERN.sub("<URL>", text)
    text = _LONGNUM_PATTERN.sub("<LONGNUM>", text)
    text = text.lower()
    text = _WHITESPACE_PATTERN.sub(" ", text).strip()
    return text
