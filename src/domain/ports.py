"""
Domain Ports

Abstract interfaces (ports) for the domain to interact with external systems.
Uses typing.Protocol for structural subtyping (duck typing).
"""

from typing import Protocol

from src.domain.entities import ClassifiedLog, Prediction


class ClassifierPort(Protocol):
    """Port for log classification services."""

    async def predict(self, text: str) -> Prediction: ...

    async def predict_batch(self, texts: list[str]) -> list[Prediction]: ...


class RouterPort(Protocol):
    """Port for routing classified logs."""

    async def route(self, log: ClassifiedLog) -> None: ...

    async def route_batch(self, logs: list[ClassifiedLog]) -> None: ...


class MetricsPort(Protocol):
    """Port for telemetry and metrics collection."""

    def increment_counter(self, name: str, value: int = 1, labels: dict[str, str] | None = None) -> None: ...

    def observe_histogram(self, name: str, value: float, labels: dict[str, str] | None = None) -> None: ...
