"""
Log Router

Routes classified logs to appropriate destinations based on category.
"""

import asyncio
from typing import Any

from src.routing.destinations import (
    BaseDestination,
    ColdStorageDestination,
    QRadarDestination,
    SummaryDestination,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)





class LogRouter:
    """
    Routes classified logs to appropriate destinations.

    Supports multiple destinations with different routing strategies:
    - immediate: Send immediately (for critical logs)
    - queue: Buffer and send in batches
    - batch: Large batch processing (for routine logs)
    - aggregate: Summarize and discard (for noise logs)
    """

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.destinations: dict[str, BaseDestination] = {}
        self.routing_rules: dict[str, dict[str, Any]] = config.get("rules", {})

        # Queues for different routing strategies
        self.queues: dict[str, asyncio.Queue] = {}
        self._workers: list[asyncio.Task] = []

    async def initialize(self):
        """Initialize routing destinations."""
        logger.info("Initializing log router...")

        # Initialize QRadar
        if "qradar" in self.config:
            self.destinations["qradar"] = QRadarDestination(self.config["qradar"])

        # Initialize cold storage
        if "cold_storage" in self.config:
            self.destinations["cold_storage"] = ColdStorageDestination(self.config["cold_storage"])

        # Initialize summary aggregator
        self.destinations["summary"] = SummaryDestination(self.config.get("summary", {}))

        # Initialize queues
        for category in ["critical", "suspicious", "routine", "noise"]:
            self.queues[category] = asyncio.Queue()

        # Start queue workers
        self._start_workers()

        logger.info("Router initialized with %s destinations", len(self.destinations))

    def _start_workers(self):
        """Start background workers for queue processing."""
        for category, queue in self.queues.items():
            worker = asyncio.create_task(self._process_queue(category, queue))
            self._workers.append(worker)

    async def _process_queue(self, category: str, queue: asyncio.Queue):
        """Process logs from a queue."""
        batch = []
        batch_size = self.routing_rules.get(category, {}).get("batch_size", 100)

        while True:
            try:
                # Wait for logs with timeout
                try:
                    log = await asyncio.wait_for(queue.get(), timeout=5.0)
                    batch.append(log)
                except TimeoutError:
                    pass

                # Process batch if full or timeout
                if len(batch) >= batch_size or (batch and queue.empty()):
                    await self._route_batch(category, batch)
                    batch = []

            except asyncio.CancelledError:
                # Process remaining logs
                while not queue.empty():
                    batch.append(await queue.get())
                if batch:
                    await self._route_batch(category, batch)
                break
            except Exception as e:
                logger.error("Error processing %s queue: %s", category, e)

    async def route(self, log: dict[str, Any]):
        """Route a single log to appropriate destinations."""
        category = log.get("category", "routine")

        rule = self.routing_rules.get(category, {})
        method = rule.get("method", "queue")

        if method == "immediate":
            await self._route_immediate(category, log)
        else:
            await self.queues.get(category, self.queues["routine"]).put(log)

    async def route_batch(self, logs: list[Any]):
        """Route a batch of classified logs."""
        for log in logs:
            # Convert ClassifiedLog to dict if needed
            if hasattr(log, "to_dict"):
                log_dict = log.to_dict()
            else:
                log_dict = log

            await self.route(log_dict)

    async def _route_immediate(self, category: str, log: dict[str, Any]):
        """Route log immediately without queuing."""
        rule = self.routing_rules.get(category, {})
        destinations = rule.get("destinations", ["qradar"])

        for dest_name in destinations:
            if dest_name in self.destinations:
                try:
                    await self.destinations[dest_name].send([log])
                except Exception as e:
                    logger.error("Failed to route to %s: %s", dest_name, e)

    async def _route_batch(self, category: str, batch: list[dict[str, Any]]):
        """Route a batch of logs."""
        if not batch:
            return

        rule = self.routing_rules.get(category, {})
        destinations = rule.get("destinations", ["cold_storage"])

        for dest_name in destinations:
            if dest_name in self.destinations:
                try:
                    await self.destinations[dest_name].send(batch)
                except Exception as e:
                    logger.error("Failed to route batch to %s: %s", dest_name, e)

    async def close(self):
        """Shutdown router and flush all queues."""
        logger.info("Shutting down router...")

        # Cancel workers
        for worker in self._workers:
            worker.cancel()

        await asyncio.gather(*self._workers, return_exceptions=True)

        # Close destinations
        for dest in self.destinations.values():
            await dest.close()

        logger.info("Router shutdown complete")
