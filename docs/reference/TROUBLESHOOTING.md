# Troubleshooting Guide

[Back to docs index](../README.md)

This guide helps diagnose and resolve common issues with the AI Log Filter system.

## Table of Contents

- [Quick Diagnostics](#quick-diagnostics)
- [Common Issues](#common-issues)
  - [1. Service Won't Start](#1-service-wont-start)
  - [2. Classification Errors](#2-classification-errors)
  - [3. Kafka Connection Issues](#3-kafka-connection-issues)
  - [4. High Latency](#4-high-latency)
  - [5. Low Accuracy](#5-low-accuracy)
  - [6. Monitoring Issues](#6-monitoring-issues)
- [ONNX Runtime Issues](#onnx-runtime-issues) 🆕
- [SPC (Statistical Process Control) Issues](#spc-statistical-process-control-issues) 🆕
- [Model Performance Issues](#model-performance-issues)
- [Environment Variables](#environment-variables)
- [Log Analysis](#log-analysis)
- [Recovery Procedures](#recovery-procedures)
- [Getting Help](#getting-help)

---

## Quick Diagnostics

Run these commands first to check system health:

```bash
# Check engine health (service mode)
curl http://localhost:8000/health

# Check REST API health
curl http://localhost:8080/health
curl http://localhost:8080/ready

# Check metrics endpoint
curl http://localhost:9090/metrics | head -50

# Check Docker containers
docker-compose ps

# View logs
docker-compose logs ai-engine --tail=100
```

---

## Common Issues

### 1. Service Won't Start

#### Symptoms
- Container exits immediately
- Health check fails

#### Diagnosis
```bash
# Check container logs
docker-compose logs ai-engine

# Check if port is in use
lsof -i :8080
lsof -i :9090
```

#### Solutions

| Issue | Solution |
|-------|----------|
| Port already in use | Stop conflicting service or change port in `.env` |
| Model files missing | Run `python scripts/validate_models.py` |
| Missing dependencies | Rebuild: `docker-compose build --no-cache` |
| Memory issues | Increase Docker memory limit |

---

### 2. Classification Errors

#### Symptoms
- API returns 500 errors
- Logs not being classified
- Circuit breaker opens

#### Diagnosis
```bash
# Check circuit breaker + classifier status (engine)
curl http://localhost:8000/health

# Check available models (REST API)
curl http://localhost:8080/models

# View error logs
docker-compose logs ai-engine 2>&1 | grep -i error
```

#### Solutions

| Issue | Solution |
|-------|----------|
| Model not loaded | Restart the API process/container to reload models |
| Circuit breaker open | Wait for timeout or restart service |
| Invalid input format | Check log format matches expected schema |
| Memory exhaustion | Scale horizontally or increase resources |

---

### 3. Kafka Connection Issues

#### Symptoms
- Logs not being consumed
- Consumer lag increasing
- Connection timeout errors

#### Diagnosis
```bash
# Check Kafka is running
docker-compose ps kafka

# List topics
docker exec kafka kafka-topics --bootstrap-server localhost:9092 --list

# Check consumer lag
docker exec kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --describe --group ai-log-filter-group
```

#### Solutions

| Issue | Solution |
|-------|----------|
| Kafka not reachable | Check `KAFKA_BOOTSTRAP_SERVERS` in `.env` |
| Topics don't exist | Create topics (see Quick Start in README) |
| Consumer group stuck | Reset offsets or restart with new group ID |
| SSL/SASL issues | Verify certificate paths and credentials |

---

### 4. High Latency

#### Symptoms
- Classification takes >100ms
- Queue backlog growing
- Metrics show high P99 latency

#### Diagnosis
```bash
# Check processing metrics
curl http://localhost:9090/metrics | grep latency

# Check CPU/memory usage
docker stats ai-engine

# Profile endpoint
time curl -X POST http://localhost:8080/classify \
  -H "Content-Type: application/json" \
  -d '{"message": "test log", "source": "test"}'
```

#### Solutions

| Issue | Solution |
|-------|----------|
| CPU saturation | Scale horizontally (add replicas) |
| Memory pressure | Increase container memory, reduce batch size |
| Model too large | Use lighter model or enable model caching |
| Network latency | Deploy closer to log sources |

---

### 5. Low Accuracy

#### Symptoms
- Critical logs being classified as routine/noise
- High false positive/negative rate
- Shadow validation failing

#### Diagnosis
```bash
# Run shadow validation
python scripts/shadow_validation.py --target-recall 0.99

# Check available models
curl http://localhost:8080/models

# Review misclassifications
cat reports/shadow_validation/false_negatives_*.csv
```

#### Solutions

| Issue | Solution |
|-------|----------|
| Model outdated | Retrain with recent data |
| Distribution shift | Add new log patterns to training data |
| Wrong weights | Adjust ensemble weights in config |
| Missing rules | Add new patterns to `configs/rules.yaml` |

---

### 6. Monitoring Issues

#### Symptoms
- Grafana dashboards empty
- Prometheus not scraping
- Alerts not firing

#### Diagnosis
```bash
# Check Prometheus targets
curl http://localhost:9091/targets

# Check Grafana datasources
curl http://localhost:3000/api/datasources

# Verify metrics are exposed
curl http://localhost:9090/metrics | grep ai_filter
```

#### Solutions

| Issue | Solution |
|-------|----------|
| Prometheus can't reach service | Check network, port mapping |
| Wrong scrape config | Verify `configs/prometheus.yml` |
| Grafana datasource misconfigured | Reconfigure datasource in Grafana UI |
| Dashboard JSON outdated | Re-import from `configs/grafana/dashboards/` |

---

## Environment Variables

Ensure these are properly set in `.env`:

| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `KAFKA_BOOTSTRAP_SERVERS` | Yes | kafka:29092 | Internal Docker network |
| `MODEL_PATH` | Yes | /app/models/latest | Path inside container |
| `LOG_LEVEL` | No | INFO | DEBUG for troubleshooting |
| `APP_ENV` | No | production | Use development for debug |

---

## Log Analysis

### Finding Errors

```bash
# All errors in last hour
docker-compose logs ai-engine --since 1h 2>&1 | grep -E "ERROR|CRITICAL"

# Classification failures
docker-compose logs ai-engine 2>&1 | grep "classification_error"

# Kafka issues
docker-compose logs ai-engine 2>&1 | grep -i kafka
```

### Common Log Patterns

| Pattern | Meaning | Action |
|---------|---------|--------|
| `CircuitBreaker opened` | Too many failures | Check upstream services |
| `Model load failed` | Model files corrupted | Redownload/retrain models |
| `Kafka consumer timeout` | Broker unreachable | Check Kafka connectivity |
| `Rate limit exceeded` | Too many requests | Implement backoff or scale |

---

## Recovery Procedures

### Full System Restart

```bash
# Stop everything
docker-compose down

# Clear volumes (if needed)
docker-compose down -v

# Rebuild and start
docker-compose up -d --build
```

### Model Recovery

```bash
# Validate current models
python scripts/validate_models.py

# If validation fails, retrain
python scripts/training_pipeline.py --data data/labeled/train.csv --output models/recovery

# Update latest symlink
ln -sfn recovery models/latest

# Restart service
docker-compose restart ai-engine
```

### Kafka Recovery

```bash
# Reset consumer group offsets
docker exec kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --group ai-log-filter-group \
  --reset-offsets --to-earliest --execute --all-topics

# Or restart with new group
export KAFKA_CONSUMER_GROUP=ai-log-filter-group-$(date +%s)
docker-compose up -d ai-engine
```

---

## Getting Help

## ONNX Runtime Issues

### Symptoms
- ONNX model fails to load
- Inference different from joblib
- Import errors for onnxruntime

### Diagnosis

```bash
# Check ONNX dependencies
python -c "import onnxruntime; print(onnxruntime.__version__)"
python -c "import skl2onnx; print(skl2onnx.__version__)"

# Validate ONNX model
python -c "from src.utils.onnx_config import print_onnx_validation; print_onnx_validation('models/v3/onnx')"

# Compare ONNX vs joblib predictions
python -c "
from src.models.onnx_runtime import compare_inference_speed
# See docs/performance/ONNX_MIGRATION_GUIDE.md for details
"
```

### Solutions

| Issue | Solution |
|-------|----------|
| `skl2onnx` not found | `uv sync --extra onnx --extra onnxruntime` (or `pip install ".[onnx,onnxruntime]"`) |
| `onnxruntime` install fails on Python 3.14 | Use Python 3.13 for ONNX runtime (or skip ONNX runtime extras) |
| ONNX model fails to load | Re-convert: `python scripts/convert_models_to_onnx.py` |
| Different predictions from joblib | Normal if < 1% difference. If higher, verify scaler loaded |
| ONNX slower than joblib | Use batch size > 50. ONNX overhead pays off at scale |
| Memory access errors | Disable memory arena in `src/models/onnx_runtime.py` |
| GPU not available | Use `onnxruntime` not `onnxruntime-gpu` for CPU-only |

### ONNX Conversion Issues

```bash
# Conversion fails with "Unknown model type"
# Solution: Ensure model is standard scikit-learn, not customized

# Conversion succeeds but model is slower
# Solution: Use batch inference, not single-item

# ONNX model larger than joblib
# Solution: Check if using old skl2onnx version, upgrade: pip install -U skl2onnx
```

---

## SPC (Statistical Process Control) Issues

### Symptoms
- SPC anomalies not detected
- Too many false positives
- Control limits not updating

### Diagnosis

```bash
# Check SPC metrics
curl http://localhost:9090/metrics | grep spc_

# View SPC stats
python -c "
from src.monitoring.spc_detector import create_siem_spc_detectors
spc = create_siem_spc_detectors()
print(spc.get_all_stats())
"
```

### Solutions

| Issue | Solution |
|-------|----------|
| No anomalies detected | Check `min_samples` threshold not reached yet |
| Too many false positives | Increase `sigma_threshold` from 3.0 to 4.0 |
| Missing temporal anomalies | Ensure `hour_of_day` feature is included |
| Control limits too wide/narrow | Adjust `window_size` (larger = smoother) |
| SPC metrics not in Prometheus | Check `spc_detector.py` is imported and running |

### SPC Tuning Guide

```python
from src.monitoring.spc_detector import SPCDetector

# For high-volume, stable metrics (e.g., EPS)
detector = SPCDetector(
    name="eps",
    window_size=300,        # 5 minutes of data
    sigma_threshold=2.5,    # Tighter threshold
    min_samples=60          # Need 1 minute of data
)

# For volatile metrics (e.g., error rate)
detector = SPCDetector(
    name="error_rate",
    window_size=60,         # 1 minute of data
    sigma_threshold=4.0,    # Loose threshold for noisy data
    min_samples=30
)
```

---

## Model Performance Issues

### High Inference Latency (> 100ms)

```bash
# Check if using ONNX (should be ~10x faster)
curl http://localhost:9090/metrics | grep onnx

# Benchmark models
python scripts/convert_models_to_onnx.py --input models/v3 --benchmark

# Check batch size (larger = more efficient)
curl http://localhost:9090/metrics | grep batch_size
```

### Solutions

| Issue | Solution |
|-------|----------|
| Still using joblib | Migrate to ONNX: see docs/performance/ONNX_MIGRATION_GUIDE.md |
| Feature extraction slow | Optimize regex patterns in `anomaly_detector.py` |
| TF-IDF vectorization slow | Pre-compute vectors or use ONNX for model only |
| Single-item inference | Batch logs: use `predict_batch()` not `predict()` |

---

## Getting Help

1. **Check logs**: `docker-compose logs ai-engine --tail=200`
2. **Run tests**: `python -m pytest tests/ -v`
3. **Check metrics**: `curl http://localhost:9090/metrics`
4. **Validate models**: `python scripts/validate_models.py`
5. **ONNX issues**: See [ONNX Migration Guide](../performance/ONNX_MIGRATION_GUIDE.md)
6. **SPC issues**: Check `src/monitoring/spc_detector.py` docstrings
7. **Review docs**: See `docs/runbooks/` for operational guides
8. **File an issue**: Include logs, metrics, and steps to reproduce
