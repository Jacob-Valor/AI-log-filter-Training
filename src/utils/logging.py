"""
Logging Configuration

Provides structured logging with JSON output support.
"""

import logging
import sys
from datetime import datetime

try:
    import structlog

    HAS_STRUCTLOG = True
except ImportError:
    HAS_STRUCTLOG = False


# Global logger cache
_loggers = {}


def setup_logging(level: str = "INFO", format_type: str = "json", output_file: str | None = None):
    """
    Configure logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_type: Output format ("json" or "text")
        output_file: Optional file path for log output
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    if HAS_STRUCTLOG and format_type == "json":
        _setup_structlog(log_level)
    else:
        _setup_standard_logging(log_level, format_type, output_file)


def _setup_structlog(log_level: int):
    """Configure structlog for JSON logging."""
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )


def _setup_standard_logging(log_level: int, format_type: str, output_file: str | None):
    """Configure standard Python logging."""
    if format_type == "json":
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)

    handlers = [console_handler]

    # File handler
    if output_file:
        file_handler = logging.FileHandler(output_file)
        file_handler.setFormatter(formatter)
        file_handler.setLevel(log_level)
        handlers.append(file_handler)

    # Configure root logger
    logging.basicConfig(level=log_level, handlers=handlers)


class JsonFormatter(logging.Formatter):
    """Custom JSON formatter for log records."""

    def format(self, record: logging.LogRecord) -> str:
        import json

        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in (
                "name",
                "msg",
                "args",
                "created",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "processName",
                "process",
                "threadName",
                "thread",
                "message",
                "msecs",
                "relativeCreated",
            ):
                log_data[key] = value

        return json.dumps(log_data)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Logger instance
    """
    if name not in _loggers:
        if HAS_STRUCTLOG:
            _loggers[name] = structlog.get_logger(name)
        else:
            _loggers[name] = logging.getLogger(name)

    return _loggers[name]


class LoggerAdapter:
    """
    Adapter to provide consistent logging interface.

    Works with both structlog and standard logging.
    """

    def __init__(self, name: str):
        self.name = name
        self._logger = get_logger(name)

    def debug(self, message: str, **kwargs):
        self._log("debug", message, **kwargs)

    def info(self, message: str, **kwargs):
        self._log("info", message, **kwargs)

    def warning(self, message: str, **kwargs):
        self._log("warning", message, **kwargs)

    def error(self, message: str, **kwargs):
        self._log("error", message, **kwargs)

    def critical(self, message: str, **kwargs):
        self._log("critical", message, **kwargs)

    def _log(self, level: str, message: str, **kwargs):
        log_method = getattr(self._logger, level)

        if HAS_STRUCTLOG:
            log_method(message, **kwargs)
        else:
            if kwargs:
                message = f"{message} | {kwargs}"
            log_method(message)
