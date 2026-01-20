#!/usr/bin/env python3
"""
Load Testing Script for AI Log Filter

Tests system performance under high throughput conditions.

This script:
1. Generates realistic log samples
2. Sends logs to the classifier at increasing rates
3. Measures latency, throughput, and error rates
4. Identifies performance bottlenecks
5. Reports whether 10K EPS target is achievable
"""

import asyncio
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class LoadTestConfig:
    """Configuration for load testing."""

    target_eps: int = 10000  # 10,000 events per second target
    duration_seconds: int = 60
    warmup_seconds: int = 10
    cooldown_seconds: int = 10
    ramp_up_steps: int = 5
    log_batch_size: int = 100
    output_path: str = "reports/load_test"


@dataclass
class LoadTestResult:
    """Results from load testing."""

    target_eps: int = 0
    achieved_eps: float = 0.0
    max_achieved_eps: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    avg_latency_ms: float = 0.0
    error_rate: float = 0.0
    total_events: int = 0
    successful_events: int = 0
    failed_events: int = 0
    duration_seconds: float = 0.0
    timestamp: str = ""

    # Per-step results
    step_results: List[Dict] = field(default_factory=list)

    @property
    def passed_target(self) -> bool:
        return self.achieved_eps >= self.target_eps

    @property
    def passed_latency(self) -> bool:
        return self.p99_latency_ms < 100  # Target: <100ms P99


class LogGenerator:
    """Generates realistic log samples for testing."""

    def __init__(self):
        # Sample log patterns
        self.log_patterns = {
            "critical": [
                "Failed login attempt from {ip} - authentication failed",
                "SQL injection attempt detected in request: {query}",
                "Unauthorized access attempt to {resource} from {ip}",
                "Malware signature detected in file {file}",
                "Brute force attack detected - {count} failed attempts from {ip}",
                "Data exfiltration attempt blocked - unusual {size} upload to {dest}",
                "Privilege escalation detected - user {user} attempted root access",
                "Critical vulnerability exploit attempt - CVE-{cve} in {component}",
                "Ransomware activity detected - encrypting {files} files",
                "Unauthorized access to sensitive data - PII exposed",
            ],
            "suspicious": [
                "Multiple failed login attempts from {ip} in {period} minutes",
                "Unusual access time detected for user {user} at {time}",
                "Configuration change detected by {user} on {resource}",
                "Port scan detected from {ip} - {ports} ports probed",
                "Failed 2FA verification for user {user}",
                "Unusual network traffic pattern detected from {ip}",
                "Abnormal data access pattern for user {user}",
                "Repeated password reset attempts for {email}",
                "Suspicious API call pattern from {source}",
                "Potential lateral movement detected",
            ],
            "routine": [
                "User {user} logged in successfully",
                "File {file} accessed by {user}",
                "Database query executed in {ms}ms",
                "API request processed successfully",
                "Cache hit for key {key}",
                "Backup completed successfully - {size} backed up",
                "Data synchronization finished for {table}",
                "Scheduled task executed: {task}",
                "Health check passed - all systems operational",
                "Configuration reloaded successfully",
            ],
            "noise": [
                "Heartbeat received from {host}",
                "Health check probe received",
                "Keepalive packet from {connection}",
                "Metric collection completed",
                "Debug trace: {trace_id}",
                "Verbose logging enabled for {component}",
                "Ping response from {host} - {ms}ms",
                "Liveness probe successful for {pod}",
                "Readiness probe successful for {pod}",
                "Telemetry data collected",
            ],
        }

        # Random value generators
        self.ips = [f"192.168.{i}.{j}" for i in range(1, 255) for j in range(1, 255)]
        self.users = [f"user{i:03d}" for i in range(1, 1000)]
        self.hosts = [f"host-{i:03d}.internal" for i in range(1, 100)]
        self.resources = [
            "/admin",
            "/api/users",
            "/db/query",
            "/files/upload",
            "/config",
        ]
        self.files = [
            f"/var/log/{name}.log" for name in ["sys", "app", "access", "error"]
        ]
        self.components = ["nginx", "apache", "mysql", "postgres", "redis", "kafka"]

    def generate(self, category: str = "routine") -> str:
        """Generate a single log message."""
        import random

        pattern = random.choice(self.log_patterns[category])

        # Replace placeholders
        replacements = {
            "{ip}": random.choice(self.ips),
            "{user}": random.choice(self.users),
            "{host}": random.choice(self.hosts),
            "{resource}": random.choice(self.resources),
            "{file}": random.choice(self.files),
            "{component}": random.choice(self.components),
            "{dest}": random.choice(self.hosts),
            "{query}": "'; DROP TABLE users;--",
            "{size}": f"{random.randint(1, 1000)}MB",
            "{count}": str(random.randint(5, 50)),
            "{period}": str(random.randint(1, 30)),
            "{time}": f"{random.randint(0, 23):02d}:{random.randint(0, 59):02d}",
            "{ports}": str(random.randint(10, 100)),
            "{email}": f"user{random.randint(1, 1000)}@example.com",
            "{source}": random.choice(self.hosts),
            "{files}": str(random.randint(100, 10000)),
            "{cve}": f"2024-{random.randint(1000, 9999)}",
            "{key}": f"cache:{random.randint(1, 10000)}",
            "{ms}": str(random.randint(1, 500)),
            "{table}": f"table_{random.randint(1, 100)}",
            "{task}": f"task_{random.randint(1, 50)}",
            "{trace_id}": f"trace-{random.randint(100000, 999999)}",
            "{connection}": f"conn-{random.randint(1, 10000)}",
            "{pod}": f"ai-log-filter-{random.randint(1, 10)}",
        }

        for placeholder, value in replacements.items():
            pattern = pattern.replace(placeholder, value)

        return pattern

    def generate_batch(
        self, count: int, category_distribution: Dict[str, int] = None
    ) -> List[str]:
        """Generate a batch of log messages."""
        import random

        if category_distribution is None:
            # Default distribution: 1% critical, 5% suspicious, 70% routine, 24% noise
            category_distribution = {
                "critical": count // 100,
                "suspicious": count // 20,
                "routine": count * 7 // 10,
                "noise": count * 24 // 100,
            }

        logs = []

        for category, num in category_distribution.items():
            logs.extend([self.generate(category) for _ in range(num)])

        # Shuffle to avoid batching by category
        random.shuffle(logs)

        # Pad to exact count
        while len(logs) < count:
            logs.append(self.generate("routine"))

        return logs[:count]


class LoadTester:
    """Performs load testing on the classifier."""

    def __init__(self, config: LoadTestConfig):
        self.config = config
        self.log_generator = LogGenerator()
        self.classifier = None
        self.results = LoadTestResult()

    async def initialize(self):
        """Initialize the classifier."""
        logger.info("Loading classifier for load testing...")

        try:
            from src.models.safe_ensemble import SafeEnsembleClassifier

            self.classifier = SafeEnsembleClassifier(model_path="models/v1", config={})
            await self.classifier.load()

            logger.info("Classifier loaded successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to load classifier: {e}")
            # Try simpler classifier
            try:
                from src.models.rule_based import RuleBasedClassifier

                self.classifier = RuleBasedClassifier("models/v1/rule_based/rules.yaml")
                logger.info("Using rule-based classifier for load testing")
                return True
            except Exception as e2:
                logger.error(f"Rule-based classifier also failed: {e2}")
                return False

    async def classify_single(self, log: str) -> Tuple[float, bool]:
        """
        Classify a single log and return latency and success.

        Returns:
            Tuple of (latency_ms, success)
        """
        start_time = time.perf_counter()

        try:
            # SafeEnsembleClassifier uses 'predict' method
            if hasattr(self.classifier, "predict"):
                pred = await self.classifier.predict(log)
                success = pred is not None
            elif hasattr(self.classifier, "classify"):
                pred = await self.classifier.classify(log)
                success = pred is not None
            else:
                # Fallback for sync classifiers
                pred = self.classifier.classify(log)
                success = pred is not None

            latency_ms = (time.perf_counter() - start_time) * 1000
            return latency_ms, success

        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.debug(f"Classification error: {e}")
            return latency_ms, False

    async def run_step(self, target_eps: int, duration: int) -> Dict:
        """Run a single load test step."""
        logger.info(f"Running load test step: {target_eps} EPS for {duration}s")

        latencies = []
        success_count = 0
        fail_count = 0
        total_events = 0

        # Calculate batch size based on target EPS
        batch_size = min(self.config.log_batch_size, max(10, target_eps // 10))
        batch_interval = batch_size / target_eps  # seconds between batches

        start_time = time.perf_counter()
        batch_num = 0

        while (time.perf_counter() - start_time) < duration:
            batch_num += 1

            # Generate batch
            logs = self.log_generator.generate_batch(batch_size)

            # Process batch concurrently
            tasks = [self.classify_single(log) for log in logs]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    fail_count += 1
                else:
                    latency, success = result
                    latencies.append(latency)
                    if success:
                        success_count += 1
                    else:
                        fail_count += 1

            total_events += len(logs)

            # Calculate current rate
            elapsed = time.perf_counter() - start_time
            if elapsed > 0 and batch_num % 10 == 0:
                current_eps = total_events / elapsed
                logger.debug(f"Current rate: {current_eps:.0f} EPS")

            # Rate limiting
            elapsed_batch = (
                time.perf_counter() - start_time - (batch_num - 1) * batch_interval
            )
            if elapsed_batch < batch_interval:
                await asyncio.sleep(batch_interval - elapsed_batch)

        # Calculate metrics
        elapsed_total = time.perf_counter() - start_time
        achieved_eps = total_events / elapsed_total if elapsed_total > 0 else 0

        return {
            "target_eps": target_eps,
            "achieved_eps": achieved_eps,
            "duration_seconds": elapsed_total,
            "total_events": total_events,
            "successful_events": success_count,
            "failed_events": fail_count,
            "latencies": latencies,
            "p50": np.percentile(latencies, 50) if latencies else 0,
            "p95": np.percentile(latencies, 95) if latencies else 0,
            "p99": np.percentile(latencies, 99) if latencies else 0,
            "max": max(latencies) if latencies else 0,
            "avg": np.mean(latencies) if latencies else 0,
        }

    async def run_load_test(self) -> LoadTestResult:
        """Run the complete load test."""
        start_time = datetime.now(timezone.utc)

        # Calculate EPS steps
        eps_steps = []
        step_size = self.config.target_eps // self.config.ramp_up_steps
        for i in range(1, self.config.ramp_up_steps + 1):
            eps_steps.append(step_size * i)

        # Add a step above target to find limits
        eps_steps.append(int(self.config.target_eps * 1.5))

        step_results = []

        # Warmup
        logger.info(f"Warmup for {self.config.warmup_seconds}s at {step_size} EPS...")
        warmup_result = await self.run_step(step_size, self.config.warmup_seconds)
        step_results.append({**warmup_result, "step_type": "warmup"})

        # Ramp up steps
        for i, target_eps in enumerate(eps_steps):
            duration = (
                self.config.duration_seconds
                if target_eps < self.config.target_eps * 1.2
                else 30
            )

            result = await self.run_step(target_eps, duration)
            result["step_type"] = "test"
            result["step_num"] = i + 1
            step_results.append(result)

            # Early exit if latency degrades
            if result["p99"] > 100:  # >100ms latency
                logger.warning(f"Latency exceeded target at {target_eps} EPS")

        # Cooldown
        logger.info(f"Cooldown at {step_size} EPS...")
        cooldown_result = await self.run_step(step_size, self.config.cooldown_seconds)
        step_results.append({**cooldown_result, "step_type": "cooldown"})

        # Aggregate results
        all_latencies = []
        total_events = 0
        successful_events = 0
        failed_events = 0
        max_eps = 0

        for sr in step_results:
            if sr["step_type"] == "test":
                all_latencies.extend(sr["latencies"])
                total_events += sr["total_events"]
                successful_events += sr["successful_events"]
                failed_events += sr["failed_events"]
                if sr["achieved_eps"] > max_eps:
                    max_eps = sr["achieved_eps"]

        self.results = LoadTestResult(
            target_eps=self.config.target_eps,
            achieved_eps=successful_events / self.config.duration_seconds
            if self.config.duration_seconds > 0
            else 0,
            max_achieved_eps=max_eps,
            p50_latency_ms=np.percentile(all_latencies, 50) if all_latencies else 0,
            p95_latency_ms=np.percentile(all_latencies, 95) if all_latencies else 0,
            p99_latency_ms=np.percentile(all_latencies, 99) if all_latencies else 0,
            max_latency_ms=max(all_latencies) if all_latencies else 0,
            avg_latency_ms=np.mean(all_latencies) if all_latencies else 0,
            error_rate=failed_events / total_events if total_events > 0 else 0,
            total_events=total_events,
            successful_events=successful_events,
            failed_events=failed_events,
            duration_seconds=(datetime.now(timezone.utc) - start_time).total_seconds(),
            timestamp=start_time.isoformat(),
            step_results=step_results,
        )

        return self.results

    def print_report(self):
        """Print load test report."""
        r = self.results

        print("\n" + "=" * 80)
        print("LOAD TEST REPORT")
        print("=" * 80)
        print(f"\nTimestamp: {r.timestamp}")
        print(f"Duration: {r.duration_seconds:.1f} seconds")

        print("\n" + "-" * 80)
        print("THROUGHPUT RESULTS")
        print("-" * 80)
        print(f"  Target EPS:           {r.target_eps:,}")
        print(f"  Achieved EPS:         {r.achieved_eps:,.0f}")
        print(f"  Max Achieved EPS:     {r.max_achieved_eps:,.0f}")
        print(f"  Target Achieved:      {'✅ YES' if r.passed_target else '❌ NO'}")

        print("\n" + "-" * 80)
        print("LATENCY RESULTS")
        print("-" * 80)
        print(f"  P50 Latency:          {r.p50_latency_ms:.2f} ms")
        print(f"  P95 Latency:          {r.p95_latency_ms:.2f} ms")
        print(f"  P99 Latency:          {r.p99_latency_ms:.2f} ms")
        print(f"  Max Latency:          {r.max_latency_ms:.2f} ms")
        print(f"  Avg Latency:          {r.avg_latency_ms:.2f} ms")
        print(f"  Target Met:           {'✅ YES' if r.passed_latency else '❌ NO'}")

        print("\n" + "-" * 80)
        print("RELIABILITY")
        print("-" * 80)
        print(f"  Total Events:         {r.total_events:,}")
        print(f"  Successful:           {r.successful_events:,}")
        print(f"  Failed:               {r.failed_events:,}")
        print(f"  Error Rate:           {r.error_rate * 100:.2f}%")

        print("\n" + "-" * 80)
        print("STEP-BY-STEP RESULTS")
        print("-" * 80)
        print(
            f"{'Step':<8} {'Target EPS':<12} {'Achieved':<12} {'P99 Latency':<12} {'Errors':<8}"
        )
        print("-" * 52)

        for sr in self.results.step_results:
            if sr["step_type"] == "test":
                print(
                    f"{sr.get('step_num', '-'):<8} "
                    f"{sr['target_eps']:<12,.0f} "
                    f"{sr['achieved_eps']:<12,.0f} "
                    f"{sr['p99']:<12.2f} "
                    f"{sr['failed_events']:<8}"
                )

        print("\n" + "=" * 80)
        print("FINAL VERDICT")
        print("=" * 80)

        if r.passed_target and r.passed_latency:
            print("✅ LOAD TEST PASSED")
            print(f"   System can handle {r.target_eps:,} EPS with <100ms P99 latency")
        elif r.passed_target:
            print("⚠️  LOAD TEST PARTIALLY PASSED")
            print("   Throughput target met but latency exceeded 100ms P99")
        else:
            print("❌ LOAD TEST FAILED")
            print(f"   Throughput target ({r.target_eps:,} EPS) not achieved")

        print("\n" + "=" * 80)

    def save_report(self):
        """Save load test report."""
        import pandas as pd

        output_dir = Path(self.config.output_path)
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        # Save JSON report
        report_path = output_dir / f"load_test_{timestamp}.json"

        report_data = {
            "timestamp": self.results.timestamp,
            "config": {
                "target_eps": self.config.target_eps,
                "duration_seconds": self.config.duration_seconds,
                "warmup_seconds": self.config.warmup_seconds,
            },
            "results": {
                "target_eps": self.results.target_eps,
                "achieved_eps": self.results.achieved_eps,
                "max_achieved_eps": self.results.max_achieved_eps,
                "p50_latency_ms": self.results.p50_latency_ms,
                "p95_latency_ms": self.results.p95_latency_ms,
                "p99_latency_ms": self.results.p99_latency_ms,
                "max_latency_ms": self.results.max_latency_ms,
                "avg_latency_ms": self.results.avg_latency_ms,
                "error_rate": self.results.error_rate,
                "total_events": self.results.total_events,
                "passed_target": self.results.passed_target,
                "passed_latency": self.results.passed_latency,
            },
            "step_results": [
                {k: v for k, v in sr.items() if k != "latencies"}
                for sr in self.results.step_results
            ],
        }

        with open(report_path, "w") as f:
            json.dump(report_data, f, indent=2)

        logger.info(f"Report saved to {report_path}")

        # Save step results to CSV
        csv_path = output_dir / f"load_test_steps_{timestamp}.csv"
        pd.DataFrame(
            [
                {k: v for k, v in sr.items() if k != "latencies"}
                for sr in self.results.step_results
            ]
        ).to_csv(csv_path, index=False)

        logger.info(f"Step results saved to {csv_path}")

        return report_path


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Load Testing")
    parser.add_argument("--target-eps", type=int, default=10000)
    parser.add_argument("--duration", type=int, default=60)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--output", default="reports/load_test")

    args = parser.parse_args()

    config = LoadTestConfig(
        target_eps=args.target_eps,
        duration_seconds=args.duration,
        warmup_seconds=args.warmup,
        output_path=args.output,
    )

    tester = LoadTester(config)

    # Initialize classifier
    if not await tester.initialize():
        logger.error("Failed to initialize classifier")
        sys.exit(1)

    # Run load test
    await tester.run_load_test()

    # Print report
    tester.print_report()

    # Save report
    tester.save_report()

    # Exit with appropriate code
    if tester.results.passed_target and tester.results.passed_latency:
        logger.info("✅ LOAD TEST PASSED")
        sys.exit(0)
    else:
        logger.info("❌ LOAD TEST FAILED")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
