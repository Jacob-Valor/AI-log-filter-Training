# Troubleshooting Guide

This guide helps diagnose and resolve common issues with the AI Log Filter system.

---

## Quick Diagnostics

Run these commands first to check system health:

```bash
# Check API health
curl http://localhost:8080/health

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
# Check circuit breaker status
curl http://localhost:8080/api/v1/circuit-breaker/status

# Check model status
curl http://localhost:8080/api/v1/models

# View error logs
docker-compose logs ai-engine 2>&1 | grep -i error
```

#### Solutions

| Issue | Solution |
|-------|----------|
| Model not loaded | Reload models: `POST /api/v1/models/reload` |
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
time curl -X POST http://localhost:8080/api/v1/classify \
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

# Check model metrics
curl http://localhost:8080/api/v1/models

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

1. **Check logs**: `docker-compose logs ai-engine --tail=200`
2. **Run tests**: `python -m pytest tests/ -v`
3. **Check metrics**: `curl http://localhost:9090/metrics`
4. **Review docs**: See `docs/runbooks/` for operational guides
5. **File an issue**: Include logs, metrics, and steps to reproduce
