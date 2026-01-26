# API Documentation

## Overview

The AI Log Filter provides a RESTful API for log classification, health monitoring, and system management.

**Base URL**: `http://localhost:8080` (development) or your production endpoint.

---

## Authentication

Currently, the API uses API key authentication via headers:

```bash
curl -H "X-API-Key: your-api-key" http://localhost:8080/api/v1/classify
```

> **Note**: For development, authentication may be disabled. Enable it in production.

---

## Endpoints

### Health & Status

#### `GET /health`

Basic health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-01-26T10:15:30.123Z"
}
```

---

#### `GET /health/ready`

Readiness probe for Kubernetes. Returns 200 if the service is ready to accept traffic.

**Response:**
```json
{
  "status": "ready",
  "models_loaded": true,
  "kafka_connected": true,
  "timestamp": "2026-01-26T10:15:30.123Z"
}
```

---

#### `GET /health/live`

Liveness probe for Kubernetes. Returns 200 if the service is alive.

**Response:**
```json
{
  "status": "alive",
  "uptime_seconds": 3600,
  "timestamp": "2026-01-26T10:15:30.123Z"
}
```

---

### Classification

#### `POST /api/v1/classify`

Classify a single log entry.

**Request Body:**
```json
{
  "message": "Failed login attempt from 192.168.1.100",
  "source": "auth-server",
  "timestamp": "2026-01-26T10:15:30.123Z",
  "metadata": {
    "user": "admin",
    "ip": "192.168.1.100"
  }
}
```

**Response:**
```json
{
  "classification": "suspicious",
  "confidence": 0.87,
  "model_version": "v3",
  "processing_time_ms": 15,
  "explanation": {
    "rule_based": {"score": 0.8, "matched_rules": ["failed_login"]},
    "tfidf_xgboost": {"score": 0.9, "top_features": ["failed", "login", "attempt"]},
    "anomaly": {"score": 0.85, "is_anomaly": false}
  }
}
```

---

#### `POST /api/v1/classify/batch`

Classify multiple log entries in a single request.

**Request Body:**
```json
{
  "logs": [
    {"message": "User logged in successfully", "source": "auth-server"},
    {"message": "Malware detected in file.exe", "source": "antivirus"},
    {"message": "Health check passed", "source": "load-balancer"}
  ]
}
```

**Response:**
```json
{
  "results": [
    {"classification": "routine", "confidence": 0.95},
    {"classification": "critical", "confidence": 0.99},
    {"classification": "noise", "confidence": 0.92}
  ],
  "total_processing_time_ms": 45,
  "model_version": "v3"
}
```

---

### Metrics

#### `GET /metrics`

Prometheus metrics endpoint.

**Response:** Prometheus text format

```
# HELP ai_filter_logs_processed_total Total number of logs processed
# TYPE ai_filter_logs_processed_total counter
ai_filter_logs_processed_total{classification="critical"} 1234
ai_filter_logs_processed_total{classification="suspicious"} 5678
ai_filter_logs_processed_total{classification="routine"} 12345
ai_filter_logs_processed_total{classification="noise"} 45678

# HELP ai_filter_classification_latency_seconds Classification latency
# TYPE ai_filter_classification_latency_seconds histogram
ai_filter_classification_latency_seconds_bucket{le="0.01"} 5000
ai_filter_classification_latency_seconds_bucket{le="0.05"} 9500
ai_filter_classification_latency_seconds_bucket{le="0.1"} 9900
```

---

### Model Management

#### `GET /api/v1/models`

List available models.

**Response:**
```json
{
  "models": [
    {
      "name": "v3",
      "status": "active",
      "loaded_at": "2026-01-26T08:00:00.000Z",
      "metrics": {
        "accuracy": 0.94,
        "critical_recall": 0.995
      }
    }
  ],
  "active_model": "v3"
}
```

---

#### `POST /api/v1/models/reload`

Reload models from disk.

**Response:**
```json
{
  "status": "success",
  "models_reloaded": ["v3"],
  "reload_time_ms": 1500
}
```

---

### Circuit Breaker

#### `GET /api/v1/circuit-breaker/status`

Get circuit breaker status.

**Response:**
```json
{
  "state": "closed",
  "failure_count": 0,
  "last_failure": null,
  "last_success": "2026-01-26T10:15:00.000Z"
}
```

---

## Error Responses

All endpoints return consistent error responses:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid log format",
    "details": {
      "field": "message",
      "issue": "Field is required"
    }
  },
  "timestamp": "2026-01-26T10:15:30.123Z"
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | Invalid request format |
| `AUTHENTICATION_ERROR` | 401 | Invalid or missing API key |
| `RATE_LIMITED` | 429 | Too many requests |
| `MODEL_ERROR` | 500 | Model prediction failed |
| `SERVICE_UNAVAILABLE` | 503 | Service temporarily unavailable |

---

## Rate Limiting

- **Default limit**: 1000 requests per minute per API key
- **Batch limit**: 100 logs per batch request
- **Circuit breaker**: Opens after 10 consecutive failures

---

## Examples

### cURL

```bash
# Classify a single log
curl -X POST http://localhost:8080/api/v1/classify \
  -H "Content-Type: application/json" \
  -d '{"message": "Failed SSH login from 192.168.1.100", "source": "sshd"}'

# Batch classification
curl -X POST http://localhost:8080/api/v1/classify/batch \
  -H "Content-Type: application/json" \
  -d '{"logs": [{"message": "Login success"}, {"message": "Malware found"}]}'
```

### Python

```python
import httpx

client = httpx.Client(base_url="http://localhost:8080")

# Classify single log
response = client.post("/api/v1/classify", json={
    "message": "Failed login attempt",
    "source": "auth-server"
})
print(response.json())

# Batch classification
response = client.post("/api/v1/classify/batch", json={
    "logs": [
        {"message": "User logged in"},
        {"message": "Malware detected"},
    ]
})
print(response.json())
```

---

## SDK Support

- **Python**: `pip install ai-log-filter-client` (coming soon)
- **JavaScript**: `npm install @ai-log-filter/client` (coming soon)
