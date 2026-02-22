from abc import ABC, abstractmethod
from typing import Any


class BaseDestination(ABC):
    """Base class for log destinations."""

    def __init__(self, name: str, config: dict[str, Any]):
        self.name = name
        self.config = config

    @abstractmethod
    async def send(self, logs: list[dict[str, Any]]):
        """Send logs to destination."""

    @abstractmethod
    async def close(self):
        """Close connection to destination."""
