# API Documentation

[Back to docs index](../README.md)

This repository exposes two HTTP surfaces:

1) **REST API** (FastAPI) for interactive classification requests.
2) **Engine health probes** (FastAPI) for Kubernetes readiness/liveness and operational status.

In `docker-compose.yaml` these are separate containers.

## Local URLs (docker-compose)

| Surface | Default URL | What it's for |
|---|---|---|
| REST API | `http://localhost:8080` | Classify logs over HTTP |
| Engine health | `http://localhost:8000` | `/health/*` probes for the ingestion/classification service |
| Prometheus metrics | `http://localhost:9090/metrics` | Scraped metrics for dashboards/alerts |

## REST API (FastAPI)

Runs with:

```bash
python -m src.main --mode api
```

### Authentication

There is **no authentication enforcement** in the current API.

Notes:
- Rate limiting will bucket clients by `X-API-Key`, `X-Client-ID`, `Authorization`, or IP (see `src/api/rate_limiter.py`).

### Endpoints

#### `GET /`

Returns basic service info.

#### `GET /health`

Basic API health check.

Response shape:
```json
{
  "status": "healthy",
  "timestamp": "2026-01-30T19:20:00Z",
  "checks": {}
}
```

#### `GET /ready`

Readiness check for the REST API process. Returns `503` if the classifier is not loaded.

#### `POST /classify`

Classify a single log.

Request body:
```json
{
  "message": "Failed login attempt for user admin",
  "source": "auth-server"
}
```

Response:
```json
{
  "category": "suspicious",
  "confidence": 0.75,
  "model": "ensemble",
  "probabilities": {"critical": 0.1, "suspicious": 0.75, "routine": 0.1, "noise": 0.05},
  "explanation": {}
}
```

#### `POST /classify/batch`

Classify a batch of logs.

Request body:
```json
{
  "logs": [
    {"message": "User logged in successfully", "source": "auth"},
    {"message": "Malware detected in file.exe", "source": "av"}
  ]
}
```

Response:
```json
{
  "results": [
    {"category": "routine", "confidence": 0.8, "model": "ensemble", "probabilities": null, "explanation": null},
    {"category": "critical", "confidence": 0.95, "model": "ensemble", "probabilities": null, "explanation": null}
  ],
  "processing_time_ms": 12.3,
  "total_logs": 2
}
```

Limits:
- Hard limit: 1000 logs per request.

#### `GET /models`

Returns the available model components.

#### `GET /stats`

Returns placeholder stats (intended to be backed by real metrics in production).

#### `POST /feedback`

Submit feedback for active learning.

This endpoint uses **query parameters**:
```text
POST /feedback?log_id=<id>&correct_category=<critical|suspicious|routine|noise>
```

#### `GET /rate-limit-status`

Returns the configured rate limits and how to interpret rate-limit headers.

### Rate limiting

Configured in `src/api/rate_limiter.py`:
- Default: `100/minute`
- `POST /classify`: `60/minute`
- `POST /classify/batch`: `30/minute`
- `POST /feedback`: `20/minute`

When rate limited, the API returns `429` and includes `Retry-After`.

## Engine health probes (FastAPI)

Runs with:

```bash
python -m src.main --mode service
```

Endpoints:

#### `GET /health`

Returns a full component health summary (classifier, Kafka, circuit breakers, and a metrics summary).

#### `GET /health/ready`

Readiness for the ingestion/classification service (used by Kubernetes readiness probe).

#### `GET /health/live`

Liveness for Kubernetes (should only fail if the process is stuck).

#### `GET /health/metrics-summary`

Convenience view of key operational metrics.

## Prometheus metrics

The engine exposes Prometheus metrics separately:

```text
GET http://localhost:9090/metrics
```

See `src/monitoring/production_metrics.py` for metric names.

## Examples

### cURL

```bash
curl -s -X POST http://localhost:8080/classify \
  -H "Content-Type: application/json" \
  -d '{"message":"Failed SSH login from 192.168.1.100","source":"sshd"}'
```

```bash
curl -s http://localhost:8000/health
```

### Python (httpx)

```python
import httpx

client = httpx.Client(base_url="http://localhost:8080")

resp = client.post("/classify", json={"message": "Failed login attempt", "source": "auth"})
resp.raise_for_status()
print(resp.json())
```
