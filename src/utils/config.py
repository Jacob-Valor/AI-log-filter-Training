"""
Configuration Management

Handles loading and validation of configuration from files and environment.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def load_config(config_path: str = "configs/config.yaml") -> dict[str, Any]:
    """
    Load configuration from YAML file with environment variable substitution.

    Args:
        config_path: Path to the YAML configuration file

    Returns:
        Dictionary with configuration values
    """
    path = Path(config_path)

    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(path) as f:
        config = yaml.safe_load(f)

    # Substitute environment variables
    config = _substitute_env_vars(config)

    return config


def _substitute_env_vars(obj: Any) -> Any:
    """
    Recursively substitute environment variables in config values.

    Supports formats:
    - ${VAR_NAME} - Required variable
    - ${VAR_NAME:default} - Variable with default value
    - ${VAR_NAME:-default} - Variable with default value (bash-style)
    """
    if isinstance(obj, dict):
        return {k: _substitute_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_substitute_env_vars(item) for item in obj]
    elif isinstance(obj, str):
        return _expand_env_var(obj)
    return obj


def _expand_env_var(value: str) -> Any:
    """Expand environment variables in a string value."""
    import re

    pattern = r"\$\{([^}:]+)(?::(-)?([^}]*))?\}"

    def replacer(match):
        var_name = match.group(1)
        default = match.group(3)

        env_value = os.environ.get(var_name)

        if env_value is not None:
            return env_value
        elif default is not None:
            return default
        else:
            return match.group(0)  # Keep original if no env var and no default

    result = re.sub(pattern, replacer, value)

    # Try to convert to appropriate type
    if result.lower() == "true":
        return True
    elif result.lower() == "false":
        return False
    elif result.isdigit():
        return int(result)

    try:
        return float(result)
    except ValueError:
        pass

    return result


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    These settings can be overridden by environment variables
    with the same name (case-insensitive).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = Field(default="ai-log-filter")
    app_env: str = Field(default="development")
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")

    # Kafka
    kafka_bootstrap_servers: str = Field(default="localhost:9092")
    kafka_input_topic: str = Field(default="raw-logs")
    kafka_consumer_group: str = Field(default="ai-log-filter-group")

    # QRadar
    qradar_host: str = Field(default="qradar.example.com")
    qradar_port: int = Field(default=443)
    qradar_token: str | None = Field(default=None)

    # Model
    model_path: str = Field(default="models/ensemble_latest")
    model_batch_size: int = Field(default=256)
    model_max_latency_ms: int = Field(default=100)

    # Thresholds
    threshold_critical: float = Field(default=0.7)
    threshold_suspicious: float = Field(default=0.6)
    threshold_noise: float = Field(default=0.8)

    # API
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    cors_allowed_origins: str = Field(
        default="*",
        description="Comma-separated list of allowed CORS origins",
    )

    # Monitoring
    prometheus_port: int = Field(default=9090)
    metrics_enabled: bool = Field(default=True)


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
