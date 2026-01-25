"""
Pytest configuration and fixtures for test isolation.

This module provides fixtures to ensure proper test isolation,
especially for Prometheus metrics which use a global registry.
"""

import pytest


def pytest_collection_modifyitems(config, items):
    """
    Reorder tests to run production_metrics tests first before
    other tests pollute the Prometheus registry.
    """
    production_metrics_tests = []
    other_tests = []

    for item in items:
        if "test_production_metrics" in str(item.fspath):
            production_metrics_tests.append(item)
        else:
            other_tests.append(item)

    # Run production_metrics tests first
    items[:] = production_metrics_tests + other_tests


@pytest.fixture(scope="function")
def fresh_eps_window():
    """Create a fresh EPSWindow instance for testing."""
    from src.monitoring.production_metrics import EPSWindow

    return EPSWindow()


@pytest.fixture(scope="function")
def fresh_metrics_collector():
    """
    Create a fresh ProductionMetricsCollector with reset internal state.
    """
    from src.monitoring.production_metrics import ProductionMetricsCollector

    collector = ProductionMetricsCollector()
    # Ensure internal counters are reset
    collector.critical_true_positives = 0
    collector.critical_false_negatives = 0
    collector.critical_false_positives = 0
    return collector
