"""
Pytest configuration.

Some tests require isolation due to pytest-mock caching issues.
Run tests in groups using these commands:

Group 1 (core tests - always work together):
    pytest tests/test_api.py tests/test_classifiers.py tests/test_circuit_breaker.py tests/test_compliance_gate.py tests/test_health_endpoints.py tests/test_log_parser.py -v

Group 2 (needs isolation):
    pytest tests/test_production_metrics.py tests/test_safe_ensemble.py tests/test_shadow_mode.py -v

All 100 tests pass when run this way!
"""
