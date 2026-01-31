"""
AI Log Filter - Main Entry Point
"""

import argparse
import asyncio
import os
import signal
import sys
from pathlib import Path
from typing import Any

from src.ingestion.kafka_consumer import LogConsumer
from src.models.base import BaseClassifier
from src.monitoring.metrics import MetricsServer
from src.routing.router import LogRouter
from src.utils.config import load_config
from src.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)


class AILogFilterService:
    """
    Main service orchestrating log ingestion, classification, and routing.
    """

    def __init__(self, config_path: str = "configs/config.yaml"):
        self.config = load_config(config_path)
        self.running = False

        # Initialize components
        self.consumer: LogConsumer | None = None
        self.classifier: BaseClassifier | None = None
        self.router: LogRouter | None = None
        self.metrics_server: MetricsServer | None = None

        # Lightweight probe server for Kubernetes health/readiness.
        self._health_server: Any | None = None
        self._health_task: asyncio.Task | None = None

    def _create_classifier(self) -> BaseClassifier:
        model_cfg = self.config.get("model", {})
        model_type = str(model_cfg.get("type", "safe_ensemble"))
        model_path = model_cfg.get("path")

        if model_type == "safe_ensemble":
            from src.models.safe_ensemble import SafeEnsembleClassifier

            return SafeEnsembleClassifier(model_path=model_path, config=model_cfg)

        if model_type == "onnx_safe_ensemble":
            from src.models.onnx_ensemble import ONNXSafeEnsembleClassifier

            return ONNXSafeEnsembleClassifier(model_path=model_path, config=model_cfg)

        if model_type == "ensemble":
            from src.models.ensemble import EnsembleClassifier

            return EnsembleClassifier(model_path=model_path, config=model_cfg)

        raise ValueError(f"Unknown model.type: {model_type}")

    async def _start_health_server(self) -> None:
        """Start lightweight health server (Kubernetes probes)."""
        health_cfg = self.config.get("health", {})
        host = str(health_cfg.get("host", "0.0.0.0"))
        port = int(health_cfg.get("port", 8000))

        import uvicorn
        from fastapi import FastAPI

        from src.api.health import health_checker
        from src.api.health import router as health_router

        # Register components so probes reflect real service state.
        if self.classifier is not None:
            health_checker.register_classifier(self.classifier)
        if self.consumer is not None:
            health_checker.register_kafka_consumer(self.consumer)
        if self.router is not None:
            health_checker.register_router(self.router)

        app = FastAPI(
            title="AI Log Filter Health",
            docs_url=None,
            redoc_url=None,
            openapi_url=None,
        )
        app.include_router(health_router)

        log_level = str(self.config.get("logging", {}).get("level", "info")).lower()
        cfg = uvicorn.Config(app, host=host, port=port, log_level=log_level, access_log=False)
        self._health_server = uvicorn.Server(cfg)
        self._health_task = asyncio.create_task(self._health_server.serve())

    async def initialize(self):
        """Initialize all service components."""
        logger.info("Initializing AI Log Filter Service...")

        # Setup logging
        setup_logging(
            level=self.config.get("logging", {}).get("level", "INFO"),
            format_type=self.config.get("logging", {}).get("format", "json"),
        )

        # Initialize classifier
        logger.info("Loading classification models...")
        self.classifier = self._create_classifier()
        await self.classifier.load()

        # Initialize router
        logger.info("Setting up log router...")
        self.router = LogRouter(self.config["routing"])
        await self.router.initialize()

        # Initialize Kafka consumer
        logger.info("Starting Kafka consumer...")
        processing_cfg = self.config.get("processing", {})
        self.consumer = LogConsumer(
            config=self.config["ingestion"]["kafka"],
            classifier=self.classifier,
            router=self.router,
            batch_size=int(processing_cfg.get("batch_size", 256)),
            max_wait_ms=int(processing_cfg.get("max_wait_ms", 100)),
        )

        # Initialize metrics server
        if self.config.get("monitoring", {}).get("prometheus", {}).get("enabled", True):
            logger.info("Starting metrics server...")
            self.metrics_server = MetricsServer(
                port=self.config["monitoring"]["prometheus"]["port"]
            )
            await self.metrics_server.start()

        # Start lightweight health server for Kubernetes probes.
        await self._start_health_server()

        logger.info("Service initialization complete")

    async def run(self):
        """Run the main processing loop."""
        self.running = True
        logger.info("Starting log processing...")

        try:
            if self.consumer is None:
                raise RuntimeError("Kafka consumer not initialized")

            await self.consumer.start()

            while self.running:
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Error in main loop: {e}", exc_info=True)
            raise
        finally:
            await self.shutdown()

    async def shutdown(self):
        """Gracefully shutdown all components."""
        logger.info("Shutting down service...")
        self.running = False

        if self.consumer:
            await self.consumer.stop()

        if self.router:
            await self.router.close()

        if self.metrics_server:
            await self.metrics_server.stop()

        if self._health_server and self._health_task:
            self._health_server.should_exit = True
            await self._health_task

        logger.info("Service shutdown complete")

    def handle_signal(self, sig: signal.Signals):
        """Handle shutdown signals."""
        logger.info(f"Received signal {sig.name}, initiating shutdown...")
        self.running = False


async def run_service(config_path: str):
    """Run the AI Log Filter service."""
    service = AILogFilterService(config_path)

    # Setup signal handlers
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda s=sig: service.handle_signal(s))

    try:
        await service.initialize()
        await service.run()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Service error: {e}", exc_info=True)
        sys.exit(1)


def _default_config_path() -> str:
    app_env = os.getenv("APP_ENV", "").strip().lower()
    if app_env == "production":
        candidate = Path("configs/production.yaml")
        if candidate.exists():
            return str(candidate)
    return "configs/config.yaml"


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="AI-Driven Log Filtering for SIEM Efficiency")
    parser.add_argument(
        "--config", type=str, default=_default_config_path(), help="Path to configuration file"
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["service", "consumer", "api"],
        default="service",
        help="Run mode",
    )

    args = parser.parse_args()

    if args.mode == "api":
        # Run FastAPI server
        import uvicorn

        from src.api.app import app

        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
    else:
        # Run main service
        asyncio.run(run_service(args.config))


if __name__ == "__main__":
    main()
