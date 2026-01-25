"""
AI Log Filter - Main Entry Point
"""

import argparse
import asyncio
import signal
import sys

from src.ingestion.kafka_consumer import LogConsumer
from src.models.ensemble import EnsembleClassifier
from src.monitoring.metrics import MetricsServer
from src.routing.router import LogRouter
from src.utils.config import Settings, load_config
from src.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)


class AILogFilterService:
    """
    Main service orchestrating log ingestion, classification, and routing.
    """

    def __init__(self, config_path: str = "configs/config.yaml"):
        self.config = load_config(config_path)
        self.settings = Settings()
        self.running = False

        # Initialize components
        self.consumer: LogConsumer | None = None
        self.classifier: EnsembleClassifier | None = None
        self.router: LogRouter | None = None
        self.metrics_server: MetricsServer | None = None

    async def initialize(self):
        """Initialize all service components."""
        logger.info("Initializing AI Log Filter Service...")

        # Setup logging
        setup_logging(
            level=self.config.get("logging", {}).get("level", "INFO"),
            format_type=self.config.get("logging", {}).get("format", "json")
        )

        # Initialize classifier
        logger.info("Loading classification models...")
        self.classifier = EnsembleClassifier(
            model_path=self.config["model"]["path"],
            config=self.config["model"]
        )
        await self.classifier.load()

        # Initialize router
        logger.info("Setting up log router...")
        self.router = LogRouter(self.config["routing"])
        await self.router.initialize()

        # Initialize Kafka consumer
        logger.info("Starting Kafka consumer...")
        self.consumer = LogConsumer(
            config=self.config["ingestion"]["kafka"],
            classifier=self.classifier,
            router=self.router
        )

        # Initialize metrics server
        if self.config.get("monitoring", {}).get("enabled", True):
            logger.info("Starting metrics server...")
            self.metrics_server = MetricsServer(
                port=self.config["monitoring"]["prometheus"]["port"]
            )
            await self.metrics_server.start()

        logger.info("Service initialization complete")

    async def run(self):
        """Run the main processing loop."""
        self.running = True
        logger.info("Starting log processing...")

        try:
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
        loop.add_signal_handler(
            sig,
            lambda s=sig: service.handle_signal(s)
        )

    try:
        await service.initialize()
        await service.run()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Service error: {e}", exc_info=True)
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="AI-Driven Log Filtering for SIEM Efficiency"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="configs/config.yaml",
        help="Path to configuration file"
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["service", "consumer", "api"],
        default="service",
        help="Run mode"
    )

    args = parser.parse_args()

    if args.mode == "api":
        # Run FastAPI server
        import uvicorn

        from src.api.app import app

        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            log_level="info"
        )
    else:
        # Run main service
        asyncio.run(run_service(args.config))


if __name__ == "__main__":
    main()
