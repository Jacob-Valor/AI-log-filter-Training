# AI-Driven Log Filtering for SIEM Efficiency

<div align="center">

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)
[![Production Ready](https://img.shields.io/badge/Status-Production%20Ready-success?style=for-the-badge)]()

[![GitHub Actions](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-2088FF?style=flat-square&logo=github-actions&logoColor=white)](https://github.com/Jacob-Valor/AI-log-filter-Training/actions)
[![codecov](https://codecov.io/gh/Jacob-Valor/AI-log-filter-Training/branch/main/graph/badge.svg)](https://codecov.io/gh/Jacob-Valor/AI-log-filter-Training)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker&logoColor=white)](Dockerfile)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-Ready-326CE5?style=flat-square&logo=kubernetes&logoColor=white)](deploy/kubernetes/)

**An intelligent ML-based log classification system for IBM QRadar SIEM**

[Quick Start](#quick-start) |
[Architecture](#architecture) |
[Documentation](docs/) |
[Contributing](CONTRIBUTING.md) |
[Security](SECURITY.md)

</div>

---

## Overview

An intelligent log classification and filtering system that reduces IBM QRadar SIEM ingestion volume by 40-60% while maintaining >99.5% critical event recall. Incoming logs are classified into four categories:

| Category       | Action                    | Description                                   |
|----------------|---------------------------|-----------------------------------------------|
| **Critical**   | QRadar (high priority)    | Immediate security threats requiring attention |
| **Suspicious** | QRadar (medium priority)  | Unusual activity warranting investigation      |
| **Routine**    | Archived to cold storage  | Normal operational logs with forensic value    |
| **Noise**      | Summarized + archived     | Low-value logs that can be filtered            |

### Design Principles

| Principle            | Implementation                                            |
|----------------------|-----------------------------------------------------------|
| **Fail-Open**        | If AI fails, all logs forward to QRadar (zero data loss)  |
| **Compliance First** | Regulated logs (PCI, HIPAA, SOX, GDPR) bypass AI entirely |
| **Zero Trust**       | Every classification logged with full explanation          |
| **Observability**    | Prometheus metrics, Grafana dashboards, audit trails       |

---

## Quick Start

### Prerequisites

- Python 3.13+
- Docker & Docker Compose (for full stack)

### Installation

```bash
git clone https://github.com/Jacob-Valor/AI-log-filter-Training.git
cd AI-log-filter-Training
```

**Option A: uv (recommended)**
```bash
uv sync --extra dev
uv run pytest -q
```

**Option B: pip**
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

**Option C: requirements files**
```bash
pip install -r requirements.txt          # production
pip install -r requirements-dev.txt      # development
```

### Validate Models

```bash
python scripts/validate_models.py
```

### Run with Docker

```bash
cp .env.example .env       # configure environment
docker-compose up -d --build
```

### Service URLs (Local)

| Service            | URL                                     | Description                        |
|--------------------|-----------------------------------------|------------------------------------|
| **REST API**       | http://localhost:8080                    | Classification endpoints           |
| **Health Probes**  | http://localhost:8000/health             | `/health`, `/health/ready`, `/health/live` |
| **Prometheus**     | http://localhost:9091                    | Metrics queries                    |
| **Grafana**        | http://localhost:3000                    | Dashboards (admin/admin)           |
| **Kafka UI**       | http://localhost:8081                    | Topics & messages                  |

---

## Architecture

> Full documentation: [Architecture Docs](docs/architecture/)

### System Overview

```
 CONTROL PLANE
 CI/CD (GitHub Actions)  |  Model Lifecycle  |  GitOps
 ─────────────────────────────────────────────────────

 LOG SOURCES                      OBSERVABILITY
 Firewalls, IDS/IPS,              Prometheus, Grafana,
 Endpoints, Cloud/Apps            AlertManager, Shadow Validator
         |                                |
         v                                |
 ┌───────────────────────────────────────────────────────────┐
 │                 INGESTION LAYER (Kafka)                    │
 │  raw-logs (12p) | classified-logs (12p) | audit-decisions  │
 └───────────────────────────┬───────────────────────────────┘
                             v
 ┌───────────────────────────────────────────────────────────┐
 │                  PROCESSING LAYER                          │
 │                                                            │
 │  ┌────────────────────────────────────────────────────┐   │
 │  │              COMPLIANCE GATE                        │   │
 │  │    PCI-DSS | HIPAA | SOX | GDPR -> BYPASS TO QRADAR│   │
 │  └─────────────────────┬──────────────────────────────┘   │
 │                        v                                   │
 │  ┌────────────────────────────────────────────────────┐   │
 │  │           SAFE ENSEMBLE CLASSIFIER                  │   │
 │  │  ┌──────────┐  ┌─────────────┐  ┌──────────────┐  │   │
 │  │  │Rule-Based│  │ TF-IDF +    │  │   Anomaly    │  │   │
 │  │  │  (30%)   │  │ XGBoost(45%)│  │ Detector(25%)│  │   │
 │  │  └────┬─────┘  └──────┬──────┘  └──────┬───────┘  │   │
 │  │       └───────────────┼────────────────┘           │   │
 │  │                       v                             │   │
 │  │            Weighted Ensemble Combiner               │   │
 │  └────────────────────────────────────────────────────┘   │
 │                        v                                   │
 │  ┌────────────────────────────────────────────────────┐   │
 │  │         CIRCUIT BREAKER (Fail-Open)                 │   │
 │  │  CLOSED -> OPEN (all -> QRadar) -> HALF_OPEN       │   │
 │  └────────────────────────────────────────────────────┘   │
 └───────────────────────────┬───────────────────────────────┘
                             v
 ┌───────────────────────────────────────────────────────────┐
 │                   ROUTING LAYER                            │
 │  CRITICAL -> QRadar (immediate)  | SUSPICIOUS -> QRadar   │
 │  ROUTINE  -> Cold Storage        | NOISE -> Summarized    │
 └───────────────────────────┬───────────────────────────────┘
                             v
 ┌───────────────────────────────────────────────────────────┐
 │                 DESTINATION LAYER                          │
 │  ┌──────────────┐  ┌───────────────┐  ┌───────────────┐  │
 │  │  IBM QRADAR  │  │ COLD STORAGE  │  │  AUDIT TRAIL  │  │
 │  │  40-60%      │  │ S3/Azure/GCS  │  │  Immutable    │  │
 │  │  reduction   │  │ Parquet+Gzip  │  │  7yr retain   │  │
 │  └──────────────┘  └───────────────┘  └───────────────┘  │
 └───────────────────────────────────────────────────────────┘
```

### Classification Pipeline

```
Log Entry -> Parse/Normalize -> Compliance Check -> Enrich -> Classify -> Route
               (5ms)             (1ms)              (10ms)    (20ms)     (5ms)
                                                                       ~ 50ms total
```

### Ensemble Classifier Weights

| Component           | Weight | Description                      |
|---------------------|--------|----------------------------------|
| **Rule-Based**      | 30%    | 40+ regex patterns, known IOCs   |
| **TF-IDF+XGBoost**  | 45%    | ML model, 10K features, n-grams  |
| **Anomaly Detector** | 25%    | Isolation Forest for outliers    |

---

## Features

### Core

- **Multi-Model Ensemble** -- Rule-based, TF-IDF+XGBoost, Anomaly Detection
- **Real-time Processing** -- <100ms latency for log classification
- **Fail-Open Safety** -- Zero data loss on system failures
- **Circuit Breaker** -- Automatic recovery from cascade failures
- **Compliance Bypass** -- PCI-DSS, HIPAA, SOX, GDPR logs skip AI
- **ONNX Inference** -- 8x faster inference, 78% smaller models ([migration guide](docs/performance/ONNX_MIGRATION_GUIDE.md))

### Integrations

- **Kafka** -- Producer/Consumer with topic management
- **QRadar** -- Native LEEF format, event submission, offense creation
- **S3** -- Cold storage for archived logs
- **Prometheus** -- 30+ operational metrics
- **Grafana** -- Production dashboard with 20+ panels

### Production

- **CI/CD** -- GitHub Actions with linting, testing, security scanning
- **Docker** -- Multi-stage build, non-root user, health checks
- **Kubernetes** -- Deployment, HPA, PDB, ServiceMonitor
- **Shadow Mode** -- Automated accuracy validation
- **Load Testing** -- 10,000+ EPS throughput validation
- **SPC Monitoring** -- Statistical process control for metric anomaly detection
- **Cost Tracking** -- Detailed cost savings analysis and reporting

---

## Performance Targets

| Metric                   | Target       |
|--------------------------|--------------|
| Classification Accuracy  | > 92%        |
| Critical Event Recall    | > 99.5%      |
| Processing Latency (P95) | < 100ms      |
| Throughput               | > 10,000 EPS |
| EPS Reduction            | 40-60%       |
| System Availability      | 99.9%        |

---

## Project Structure

```
ai-log-filter/
├── src/                          # Source code
│   ├── api/                      # FastAPI endpoints, rate limiting
│   ├── ingestion/                # Kafka consumers, log parsers
│   ├── preprocessing/            # Compliance gate, data cleaning
│   ├── models/                   # ML models
│   │   ├── base.py               # Base classifier interface
│   │   ├── ensemble.py           # Ensemble classifier
│   │   ├── safe_ensemble.py      # Production-safe ensemble (fail-open)
│   │   ├── tfidf_classifier.py   # TF-IDF + XGBoost
│   │   ├── anomaly_detector.py   # Isolation Forest
│   │   ├── rule_based.py         # Pattern matching rules
│   │   ├── onnx_converter.py     # ONNX model converter
│   │   └── onnx_runtime.py       # ONNX inference runtime
│   ├── monitoring/               # Prometheus metrics, SPC detector, cost tracking
│   ├── routing/                  # Log routing logic (QRadar, cold storage)
│   ├── validation/               # Shadow mode, QRadar correlation
│   ├── integration/              # Kafka, QRadar, common utilities
│   └── utils/                    # Config, logging, circuit breaker
│
├── configs/                      # Configuration files
│   ├── config.yaml               # Main configuration
│   ├── production.yaml           # Production overrides
│   ├── model_config.yaml         # ML model configuration
│   ├── rules.yaml                # Classification rules (40+)
│   ├── prometheus.yml            # Prometheus config
│   └── grafana/                  # Grafana dashboard provisioning
│
├── models/                       # Trained model artifacts
├── data/                         # Training data (labeled, raw, samples)
├── scripts/                      # Utility scripts (see below)
├── tests/                        # Test suite (129 tests)
├── docs/                         # Documentation
│
├── .github/workflows/            # CI/CD pipelines (ci.yml, cd.yml)
├── deploy/                       # Kubernetes manifests
├── Dockerfile                    # Multi-stage container build
├── docker-compose.yml            # Local development stack
├── Makefile                      # Build automation
├── pyproject.toml                # Project metadata & tooling config
└── requirements.txt              # Production dependencies
```

---

## Scripts Reference

All scripts are in the `scripts/` directory. Run from the project root.

<details>
<summary><strong>Data Generation & Preparation</strong></summary>

#### `generate_sample_data.py` -- Generate Synthetic Training Data

```bash
python scripts/generate_sample_data.py                                    # 10K samples (default)
python scripts/generate_sample_data.py --samples 5000 --test-split        # with test split
python scripts/generate_sample_data.py --output data/labeled/custom.csv   # custom path
```

| Option         | Default                  | Description                      |
|----------------|--------------------------|----------------------------------|
| `--output`     | `data/labeled/train.csv` | Output CSV file path             |
| `--samples`    | `10000`                  | Number of samples to generate    |
| `--test-split` | `false`                  | Also generate test.csv (20%)     |

</details>

<details>
<summary><strong>Model Training & Evaluation</strong></summary>

#### `train.py` -- Basic Model Training

```bash
python scripts/train.py --model-type all          # train all models
python scripts/train.py --model-type tfidf         # TF-IDF only
python scripts/train.py --model-type anomaly       # anomaly detector only
```

| Option         | Default                    | Description                   |
|----------------|----------------------------|-------------------------------|
| `--config`     | `configs/model_config.yaml`| Model configuration           |
| `--model-type` | `all`                      | `tfidf`, `anomaly`, `all`     |
| `--output`     | `models`                   | Output directory              |

#### `training_pipeline.py` -- Full Training Pipeline

```bash
python scripts/training_pipeline.py --data data/labeled/train.csv --output models/v3
python scripts/training_pipeline.py --hdfs HDFS_v3_TraceBench/ --auto-label --output models/v3
```

| Option          | Default      | Description                     |
|-----------------|--------------|---------------------------------|
| `--data`        | --           | Path to labeled CSV             |
| `--hdfs`        | --           | Path to HDFS TraceBench dir     |
| `--auto-label`  | `false`      | Auto-label using patterns       |
| `--output`      | `models/v3`  | Output directory                |
| `--min-recall`  | `0.99`       | Minimum critical recall         |

#### `evaluate.py` -- Model Evaluation

```bash
python scripts/evaluate.py --model models/latest --test-data data/labeled/test.csv
python scripts/evaluate.py --model models/v3 --test-data data/labeled/test.csv --output results.json
```

</details>

<details>
<summary><strong>Validation & Testing</strong></summary>

#### `validate_models.py` -- Model Artifact Validation

```bash
python scripts/validate_models.py
```

#### `shadow_validation.py` -- Shadow Mode Testing

```bash
python scripts/shadow_validation.py
python scripts/shadow_validation.py --model-path models/v2 --target-recall 0.995
```

| Option            | Default                   | Description                 |
|-------------------|---------------------------|-----------------------------|
| `--model-path`    | `models/latest`           | Model directory             |
| `--test-data`     | `data/labeled/test.csv`   | Test data path              |
| `--target-recall` | `0.995`                   | Target critical recall      |

#### `load_test.py` -- Performance/Load Testing

```bash
python scripts/load_test.py --target-eps 100 --duration 5      # quick test
python scripts/load_test.py --target-eps 10000 --duration 60    # full test
```

#### `chaos_test.py` -- Chaos/Resilience Testing

```bash
python scripts/chaos_test.py
```

Tests: fail-open, circuit breaker, high latency, concurrent load, memory pressure, critical recall under stress, graceful degradation, recovery after failure.

#### `integration_tests.py` -- Integration Testing

```bash
python scripts/integration_tests.py --kafka --kafka-brokers localhost:9092
python scripts/integration_tests.py --qradar --qradar-host qradar.example.com --qradar-token TOKEN
python scripts/integration_tests.py --s3 --s3-bucket your-bucket
```

</details>

<details>
<summary><strong>Reports & Utilities</strong></summary>

#### `cost_report.py` -- Cost Savings Report

```bash
python scripts/cost_report.py --format terminal
python scripts/cost_report.py --format markdown --output docs/COST_REPORT.md
python scripts/cost_report.py --format json --qradar-eps 20000
```

#### `cleanup.sh` -- Project Cleanup (interactive)

```bash
bash scripts/cleanup.sh
```

</details>

---

## Configuration

### Main Configuration (`configs/config.yaml`)

```yaml
ingestion:
  kafka:
    bootstrap_servers: "localhost:9092"
    consumer:
      group_id: "ai-log-filter"
      auto_offset_reset: "earliest"
    topics:
      input: "raw-logs"
      output: "filtered-logs"

processing:
  batch_size: 256
  max_wait_ms: 100

model:
  type: "safe_ensemble"
  path: "models/latest"
  timeout_seconds: 5.0
  max_batch_size: 1000
  ensemble:
    weights:
      rule_based: 0.30
      tfidf_xgboost: 0.45
      anomaly_detector: 0.25

routing:
  qradar:
    host: "qradar.example.com"
    token: "${QRADAR_TOKEN}"
  cold_storage:
    type: "s3"
    bucket: "ai-log-filter-logs"

monitoring:
  prometheus:
    enabled: true
    port: 9090
```

### Compliance Bypass

Regulated log patterns automatically bypass AI filtering:

| Regulation | Patterns                                  | Retention    |
|------------|-------------------------------------------|--------------|
| PCI-DSS    | `pci_*`, `payment_*`, `cardholder_*`      | 365 days     |
| HIPAA      | `hipaa_*`, `ehr_*`, `patient_*`, `phi_*`  | 6 years      |
| SOX        | `financial_*`, `trading_*`, `audit_*`     | 7 years      |
| GDPR       | `gdpr_*`, `pii_*`                         | Configurable |

### Environment Variables

| Variable                    | Default               | Description                        |
|-----------------------------|-----------------------|------------------------------------|
| `APP_ENV`                   | `development`         | Application environment            |
| `LOG_LEVEL`                 | `INFO`                | Logging level                      |
| `KAFKA_BOOTSTRAP_SERVERS`   | `kafka:29092`         | Kafka broker addresses             |
| `KAFKA_INPUT_TOPIC`         | `raw-logs`            | Input topic                        |
| `KAFKA_OUTPUT_TOPIC`        | `filtered-logs`       | Output topic                       |
| `MODEL_TYPE`                | `safe_ensemble`       | Model selection                    |
| `MODEL_PATH`                | `/app/models/latest`  | Model directory                    |
| `HEALTH_PORT`               | `8000`                | Health server port                 |
| `PROMETHEUS_PORT`           | `9090`                | Metrics server port                |

---

## Production Deployment

### 1. Validate

```bash
python scripts/validate_models.py
python scripts/shadow_validation.py --target-recall 0.995
python scripts/load_test.py --target-eps 10000
python scripts/integration_tests.py --kafka --qradar --s3
```

### 2. Deploy

```bash
kubectl apply -f deploy/kubernetes/deployment.yaml
```

### 3. Monitor

Import `configs/grafana/dashboards/production.json` into Grafana.

Dashboard panels cover: EPS reduction, classification quality (precision/recall/F1), circuit breaker state, compliance bypasses, system health, drift detection.

```bash
curl http://localhost:8000/health          # full health check
curl http://localhost:8000/health/ready     # readiness probe
curl http://localhost:8000/health/live      # liveness probe
curl http://localhost:9090/metrics | grep ai_filter_   # Prometheus metrics
```

Key metrics:
- `ai_filter_eps_reduction_ratio` -- target: 40-60%
- `ai_filter_critical_recall` -- target: >99.5%
- `ai_filter_classification_latency` -- target: <100ms P99
- `ai_filter_circuit_breaker_state` -- 0=closed, 1=open (alert)

### 4. Train SOC Team

See [`docs/training/SOC_TRAINING_GUIDE.md`](docs/training/SOC_TRAINING_GUIDE.md).

---

## Model Training

```bash
# 1. Prepare labeled data
python scripts/generate_sample_data.py --samples 10000 --test-split

# 2. Train
python scripts/train.py --data data/labeled/train.csv --model-type all --output models/v3

# 3. Evaluate
python scripts/evaluate.py --model models/v3 --test-data data/labeled/test.csv

# 4. Validate
python scripts/validate_models.py
```

---

## Contributing

Contributions welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for community standards.

```bash
git checkout -b feature/your-feature
git commit -m 'Add your feature'
git push origin feature/your-feature
# Open a Pull Request
```

---

## License

MIT License -- see [LICENSE](LICENSE).

## Security

See [SECURITY.md](SECURITY.md) for reporting vulnerabilities.

## Acknowledgments

- [IBM QRadar](https://www.ibm.com/qradar) | [Apache Kafka](https://kafka.apache.org/) | [scikit-learn](https://scikit-learn.org/) | [XGBoost](https://xgboost.readthedocs.io/) | [Prometheus](https://prometheus.io/) | [Grafana](https://grafana.com/)

---

<div align="center">

**Last Updated:** February 2026

</div>
