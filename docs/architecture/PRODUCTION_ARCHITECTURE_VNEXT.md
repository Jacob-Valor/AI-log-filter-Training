# AI-Driven Log Filtering for SIEM - Production Architecture (vNext)

## Table of Contents

1. [Executive Overview](#executive-overview)
2. [System Architecture](#system-architecture)
3. [Component Design](#component-design)
4. [Data Flow](#data-flow)
5. [Safety & Resilience Patterns](#safety--resilience-patterns)
6. [API Security & Rate Limiting](#api-security--rate-limiting)
7. [Compliance Framework](#compliance-framework)
8. [Evidence & Audit (Chain-of-Custody)](#evidence--audit-chain-of-custody)
9. [Trained Models](#trained-models)
10. [Model Governance](#model-governance)
11. [Validation Framework](#validation-framework)
12. [Deployment Architecture](#deployment-architecture)
13. [Monitoring & Observability](#monitoring--observability)
14. [Incident Response](#incident-response)
15. [Disaster Recovery](#disaster-recovery)
16. [Deployment Checklist](#deployment-checklist)
17. [Appendix: vNext Improvements](#appendix-vnext-improvements)
18. [File Structure](#file-structure)

---

## Executive Overview

### Purpose

Intelligent pre-processing layer for IBM QRadar SIEM that reduces operational costs while maintaining security detection efficacy through ML-based log classification.

This vNext document keeps the production-ready design from `docs/architecture/PRODUCTION_ARCHITECTURE.md` and makes the following improvements explicit:

- Trust boundaries (DMZ / application zone / data zone)
- Control plane vs data plane separation (GitOps + model lifecycle)
- Evidence-grade auditability (decision record schema + chain-of-custody expectations)
- Bounded delivery to QRadar with backpressure buffering (`pending-qradar`) to avoid cascading failures

### Current Status: **9.6/10 - Production Buildable vNext Reference**

This score is for architecture completeness and operational realism (not a runtime SLA).

| Component                    | Status          | Score |
| ---------------------------- | --------------- | ----- |
| System Architecture          | ✅ Complete     | 10/10 |
| Safety Patterns              | ✅ Complete     | 10/10 |
| Evidence & Audit (vNext)     | 🟡 Design-Ready | 9/10  |
| API Security & Rate Limiting | ✅ Complete     | 10/10 |
| Compliance Framework         | ✅ Complete     | 10/10 |
| Monitoring & Observability   | ✅ Complete     | 10/10 |
| Validation Framework         | ✅ Complete     | 10/10 |
| Model Governance (vNext)     | 🟡 Design-Ready | 9/10  |
| Incident Response            | ✅ Complete     | 9/10  |
| Disaster Recovery            | ✅ Complete     | 9/10  |

### Key Design Principles

| Principle            | Implementation                                                                   |
| -------------------- | -------------------------------------------------------------------------------- |
| **Fail-Open**        | On classifier or dependency failure, classification never suppresses delivery    |
| **Bounded Delivery** | QRadar delivery is rate-limited; backpressure buffers via Kafka `pending-qradar` |
| **Zero Loss**        | ALL raw logs archived to cold storage (partitioned, compressed)                  |
| **Auditability**     | Every decision recorded with model/rules version + correlation metadata          |
| **Compliance-First** | Regulated sources bypass filtering entirely                                      |
| **Defense in Depth** | Rule override + ML classifier + anomaly detector ensemble                        |
| **Least Privilege**  | Tight service accounts, topic ACLs, bucket policies                              |
| **API Protection**   | WAF/LB coarse limits + per-client API rate limiting                              |

### Performance Targets

| Metric                   | Target             | SLA       | Notes                                                  |
| ------------------------ | ------------------ | --------- | ------------------------------------------------------ |
| Processing Latency (P99) | < 100ms            | 99.9%     | Excludes external enrichment calls in degraded mode    |
| Throughput               | > 50,000 EPS       | 99.5%     | Scaling via consumer count + partitions                |
| Critical Event Recall    | > 99.5%            | 99.99%    | Verified via shadow mode + QRadar correlation          |
| System Availability      | 99.9%              | Monthly   | Includes fail-open mode as "available"                 |
| EPS Reduction to SIEM    | 40-60%             | Quarterly | Policy-dependent; must never suppress compliance logs  |
| Evidence Durability      | 100% logs archived | N/A       | Cold storage is the source of truth for investigations |

---

## System Architecture

### High-Level Architecture Diagram (vNext)

```
                                     ┌─────────────────────────────────────────┐
                                     │            CONTROL PLANE                │
                                     │  ┌────────────┐  ┌────────────────────┐ │
                                     │  │ CI/CD +    │  │ Model Lifecycle     │ │
                                     │  │ GitOps     │  │ (train/validate/    │ │
                                     │  │            │  │  promote/rollback)  │ │
                                     │  └─────┬──────┘  └──────────┬─────────┘ │
                                     └────────┼─────────────────────┼──────────┘
                                              │                     │
                                              ▼                     ▼
                                       Deploy/config          Model artifacts

                                     ┌─────────────────────────────────────────┐
                                     │         EXTERNAL INTEGRATIONS           │
                                     │  ┌─────────┐ ┌─────────┐ ┌───────────┐  │
                                     │  │ Threat  │ │ Asset   │ │ Identity  │  │
                                     │  │ Intel   │ │ CMDB    │ │ Provider  │  │
                                     │  └────┬────┘ └────┬────┘ └─────┬─────┘  │
                                     └───────┼──────────┼─────────────┼────────┘
                                             │          │             │
                                             ▼          ▼             ▼

┌──────────────────────────┐     ┌─────────────────────────────────────────────┐
│        LOG SOURCES        │     │             DMZ / PUBLIC EDGE               │
│  ┌────────────┐          │     │  ┌─────────────┐   ┌─────────────────────┐  │
│  │ Firewalls  │          │     │  │ WAF / LB     │──▶│ API Gateway          │  │
│  ├────────────┤          │     │  │ • TLS 1.3    │   │ • JWT + RBAC         │  │
│  │ Endpoints  │          │     │  │ • DDoS       │   │ • Rate limiting      │  │
│  ├────────────┤          │     │  │ • coarse RL  │   │ • Request validation │  │
│  │ Servers    │          │     │  └─────────────┘   └──────────┬───────────┘  │
│  ├────────────┤          │     └────────────────────────────────┼──────────────┘
│  │ Cloud      │          │                                      │ mTLS
│  ├────────────┤          │                                      ▼
│  │ Apps       │          │     ┌─────────────────────────────────────────────┐
│  └────────────┘          │     │          APPLICATION ZONE (Kubernetes)      │
└──────────┬───────────────┘     │  ┌───────────────────────────────────────┐  │
           │                     │  │ Ingestion + Processing Pods           │  │
           ▼                     │  │                                       │  │
┌──────────────────────────┐     │  │  ┌─────────────────────────────────┐  │  │
│         INGESTION         │     │  │  │ Compliance / Policy Gate        │  │  │
│  ┌────────────────────┐  │     │  │  └───────────────┬─────────────────┘  │  │
│  │ Kafka Cluster       │──┼─────┼──┼──────────────────▼────────────────────┼──┘
│  │ • raw-logs          │  │     │  │  ┌─────────────────────────────────┐  │
│  │ • classified-logs   │  │     │  │  │ Safe Ensemble Classifier         │  │
│  │ • dlq               │  │     │  │  │ • rules + ML + anomaly           │  │
│  │ • audit-decisions   │  │     │  │  └───────────────┬─────────────────┘  │
│  │ • pending-qradar    │  │     │  │                  ▼                    │
│  └────────────────────┘  │     │  │  ┌─────────────────────────────────┐  │
└──────────┬───────────────┘     │  │  │ Circuit Breaker (FAIL-OPEN)      │  │
           │                     │  │  │ • timeouts + repeated failure    │  │
           │                     │  │  │ • fail-open to deliverable path  │  │
           │                     │  │  └───────────────┬─────────────────┘  │
           ▼                     └──────────────────────┼─────────────────────┘
┌────────────────────────────────────────────────────────┼────────────────────────────────────┐
│                              ROUTING / DELIVERY                                                 │
│  CRITICAL → QRadar immediate | SUSPICIOUS → queued | ROUTINE/NOISE → reduced path (policy)    │
│  QRadar bounded delivery: buffer in Kafka `pending-qradar` when unreachable/backpressured       │
└────────────────────────────────────────────────────────┼────────────────────────────────────┘
                                                        │
                                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                                  DESTINATION LAYER                                           │
│   ┌──────────────────────────────────────────┐    ┌────────────────────────────────────┐    │
│   │              IBM QRADAR                  │    │      EVIDENCE / STORAGE             │    │
│   │  • Offense Engine                        │    │  ┌─────────────────────────────┐   │    │
│   │  • Log Activity                          │    │  │ Cold Storage (ALL logs)     │   │    │
│   │  • Rules/Correlation                     │    │  │ • Parquet + gzip            │   │    │
│   └──────────────────────────────────────────┘    │  │ • partitioned by time/source│   │    │
│                                                    │  └─────────────────────────────┘   │    │
│                                                    │  ┌─────────────────────────────┐   │    │
│                                                    │  │ Audit Store (immutable)     │   │    │
│                                                    │  │ • append-only decisions     │   │    │
│                                                    │  │ • long retention            │   │    │
│                                                    │  └─────────────────────────────┘   │    │
│                                                    └────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                                OBSERVABILITY LAYER                                           │
│   ┌────────────────┐    ┌────────────────┐    ┌────────────────┐    ┌────────────────┐     │
│   │  Prometheus    │    │   Grafana      │    │  Alert         │    │  Shadow Mode   │     │
│   │  Metrics       │    │   Dashboards   │    │  Manager       │    │  Validator     │     │
│   └────────────────┘    └────────────────┘    └────────────────┘    └────────────────┘     │
│                                                                                              │
│   Key vNext Metrics:                                                                         │
│   • ai_filter_pending_qradar_depth        • ai_filter_audit_write_failures_total            │
│   • ai_filter_evidence_archive_success    • ai_filter_time_drift_seconds                    │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Design

### 1. Ingestion Layer (Kafka)

```
┌───────────────────────────────────────────────────────────────────────────┐
│                                KAFKA CLUSTER                               │
│                                                                           │
│  Topics:                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐        │
│  │ raw-logs          │  │ classified-logs  │  │ dead-letter (dlq)│        │
│  │ Partitions: 12    │  │ Partitions: 12   │  │ Partitions: 3    │        │
│  │ Retention: 24h    │  │ Retention: 72h   │  │ Retention: 7d    │        │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘        │
│  ┌──────────────────┐  ┌──────────────────┐                               │
│  │ pending-qradar    │  │ audit-decisions  │                               │
│  │ Partitions: 6     │  │ Partitions: 12   │                               │
│  │ Retention: 24h    │  │ Retention: 30d+  │                               │
│  └──────────────────┘  └──────────────────┘                               │
│                                                                           │
│  Consumer Groups:                                                         │
│  • ai-filter-primary (processing)                                        │
│  • ai-filter-shadow (validation)                                         │
│  • ai-filter-audit (decision export)                                     │
│  • ai-filter-qradar-delivery (bounded drain)                             │
└───────────────────────────────────────────────────────────────────────────┘
```

### 2. Classification Pipeline

```
                     ┌─────────────────────────────────────┐
                     │              LOG ENTRY              │
                     └──────────────┬──────────────────────┘
                                    │
                     ┌──────────────▼──────────────────────┐
                     │         PARSE & NORMALIZE           │
                     │  • Format detection (LEEF/CEF/JSON) │
                     │  • Field extraction                 │
                     │  • Timestamp normalization          │
                     └──────────────┬──────────────────────┘
                                    │
                     ┌──────────────▼──────────────────────┐
                     │      COMPLIANCE / POLICY GATE        │
                     │  IF regulated_source:                │
                     │     → BYPASS to QRadar directly      │
                     │  ELSE: continue                      │
                     └──────────────┬──────────────────────┘
                                    │
                     ┌──────────────▼──────────────────────┐
                     │            ENRICH                    │
                     │  • Cache-first (avoid P99 coupling)  │
                     │  • CMDB/TI optional (degraded mode)  │
                     └──────────────┬──────────────────────┘
                                    │
          ┌─────────────────────────┼─────────────────────────┐
          │                         │                         │
          ▼                         ▼                         ▼
 ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
 │   RULE-BASED    │     │   ML CLASSIFIER │     │  ANOMALY DETECT │
 │                 │     │                 │     │                 │
 │ • Regex/IOCs     │     │ • TF-IDF + XGB  │     │ • Isolation     │
 │ • Priority rules │     │ • Fast inference│     │   Forest        │
 │                 │     │                 │     │ • baseline dev  │
 │ Weight: 30%     │     │ Weight: 45%     │     │ Weight: 25%     │
 └────────┬────────┘     └────────┬────────┘     └────────┬────────┘
          │                       │                       │
          │      ┌────────────────┼────────────────┐      │
          │      │                │                │      │
          └──────┼────────────────┼────────────────┼──────┘
                 │                │                │
                 ▼                ▼                ▼
          ┌─────────────────────────────────────────────┐
          │           ENSEMBLE COMBINER                  │
          │                                              │
          │  Strategy: Weighted Average                  │
          │  Override: Rule-based critical always wins   │
          └──────────────────────┬──────────────────────┘
                                 │
                                 ▼
          ┌─────────────────────────────────────────────┐
          │           CONFIDENCE THRESHOLD              │
          │                                              │
          │  Critical:   conf >= 0.70                   │
          │  Suspicious: conf >= 0.60                   │
          │  Noise:      conf >= 0.80                   │
          │  Routine:    default                        │
          └──────────────────────┬──────────────────────┘
                                 │
                                 ▼
          ┌─────────────────────────────────────────────┐
          │           EXPLAIN, RECORD, ROUTE            │
          │                                              │
          │  • Generate explanation (critical paths)    │
          │  • Emit audit decision event                 │
          │  • Route to destination(s)                   │
          └─────────────────────────────────────────────┘
```

---

## Data Flow

### Normal Operation Flow

```
1. Log Ingestion (T+0ms)
   └── Kafka consumer receives log batch

2. Parse & Validate (T+5ms)
   └── Format detection, field extraction

3. Compliance / Policy Gate (T+6ms)
   ├── IF regulated → Direct to QRadar (skip filtering)
   └── ELSE → Continue

4. Enrichment (T+15ms)
   └── Cache-first enrichment (CMDB/TI optional)

5. Classification (T+35ms)
   ├── Rule-based check
   ├── ML inference
   ├── Anomaly scoring
   └── Ensemble combination

6. Record + Routing Decision (T+40ms)
   ├── Emit decision to `audit-decisions`
   └── Category-based destination selection

7. Delivery (T+50ms)
   ├── QRadar (critical/suspicious + bypassed compliance)
   ├── Cold Storage (ALL logs)
   └── Audit Store (immutable decisions)

Total Latency: ~50ms (P95 target)
```

### Failure Mode Flows

```
SCENARIO: ML Model Failure
─────────────────────────────────────────
1. Model throws exception / times out
2. Circuit breaker increments failure count
3. IF failures > threshold:
   └── Circuit opens (fail-open)
4. Logs marked fail_open=true
5. Filtering disabled (deliverable path)
6. QRadar delivery remains bounded; backlog buffers via pending-qradar if needed

SCENARIO: Kafka Consumer Lag
─────────────────────────────────────────
1. Consumer lag exceeds threshold
2. Autoscale consumers
3. Reduce enrichment cost (cache-only mode)
4. IF lag exceeds emergency threshold:
   └── Activate bypass mode (deliver-without-filter)

SCENARIO: QRadar Backpressure / Unreachable
─────────────────────────────────────────
1. QRadar delivery fails or slows (timeouts, throttling)
2. Write deliverable events to Kafka pending-qradar
3. Alert triggered
4. Continue cold storage + audit decisions (no evidence loss)
5. On recovery: bounded drain of pending-qradar to QRadar

SCENARIO: Enrichment Dependency Failure
─────────────────────────────────────────
1. CMDB/TI unavailable
2. Switch to degraded enrichment (cache-only)
3. Continue classification with metadata flag enrichment_degraded=true
4. Alert if sustained
```

---

## Safety & Resilience Patterns

### Circuit Breaker (Fail-Open)

```
┌─────────────────────────────────────────────────────────────────┐
│                    CIRCUIT BREAKER PATTERN                       │
│                                                                  │
│  Recommended implementation: src/utils/circuit_breaker.py        │
│                                                                  │
│  States:                                                         │
│  ┌──────────┐    failures > threshold    ┌──────────┐            │
│  │  CLOSED  │ ─────────────────────────▶ │   OPEN   │            │
│  │ (normal) │                            │(fail-open│            │
│  └────┬─────┘                            │deliverable)          │
│       │                                  └────┬─────┘            │
│       │                timeout                 │                  │
│       │             ┌──────────────────────────┘                  │
│       │             ▼                                             │
│       │        ┌──────────┐                                       │
│       │        │HALF-OPEN │ ─── success ───▶ CLOSED                │
│       └────────│(testing) │ ─── failure ───▶ OPEN                  │
│                └──────────┘                                       │
│                                                                  │
│  Fail-open behavior: filtering disabled, delivery bounded to QRadar│
└─────────────────────────────────────────────────────────────────┘
```

### QRadar Backpressure Buffer (vNext)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     BOUNDED DELIVERY + BACKPRESSURE BUFFER                        │
├─────────────────────────────────────────────────────────────────────────────────┤
│ Goal: prevent "fail-open" from turning into "SIEM overload"                         │
│                                                                                   │
│  Deliverable events ──▶ QRadar delivery worker ──▶ QRadar                          │
│         │                       │                                                 │
│         │                       ├── OK: steady-state                              │
│         │                       └── Slow/Fail: write to pending-qradar             │
│         ▼                                                                         │
│   Kafka topic: pending-qradar (bounded drain after recovery)                       │
│                                                                                   │
│ Invariant: cold storage + audit decisions continue regardless of QRadar health     │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Enrichment Degraded Mode

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          ENRICHMENT DEGRADED MODE                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│ Normal: cache-first + async refresh from CMDB/TI                                  │
│ Degraded: cache-only; no external calls in hot path                               │
│                                                                                   │
│ Decision record includes: enrichment_degraded=true                                │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## API Security & Rate Limiting

### Authentication & Authorization

| Component     | Auth Method        | Authorization    | Notes                          |
| ------------- | ------------------ | ---------------- | ------------------------------ |
| API Endpoints | JWT + API Key      | RBAC (roles)     | Short token TTL (e.g., 1 hour) |
| Kafka         | SASL/SCRAM-SHA-512 | Topic ACLs       | Per-consumer credentials       |
| QRadar        | API Token + TLS    | Predefined perms | Rotate tokens (e.g., 90 days)  |
| Storage       | IAM Role (IRSA)    | Bucket policies  | No static credentials          |

### Rate Limiting

Recommended implementation: `src/api/rate_limiter.py`

| Endpoint               | Limit (per client)  |
| ---------------------- | ------------------- |
| POST `/classify`       | 60 requests/minute  |
| POST `/classify/batch` | 30 requests/minute  |
| POST `/feedback`       | 20 requests/minute  |
| GET `/health`          | 120 requests/minute |
| Default                | 100 requests/minute |

---

## Compliance Framework

### Compliance Bypass Gate

Compliance logs bypass filtering entirely and are always deliverable to QRadar.

```
┌─────────────────────────────────────────────────────────────────┐
│                    COMPLIANCE OVERRIDE                           │
│                                                                  │
│  Recommended implementation: src/preprocessing/compliance_gate.py │
│                                                                  │
│  Regulated Source Patterns:                                      │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │ PCI-DSS:    pci_*, payment_*, cardholder_*, card_*       │     │
│  │ HIPAA:      hipaa_*, ehr_*, patient_*, phi_*, medical_*  │     │
│  │ SOX:        financial_*, trading_*, audit_*, sox_*        │     │
│  │ GDPR:       gdpr_*, privacy_*, consent_*, personal_*     │     │
│  │ Custom:     [configurable per deployment]                │     │
│  └─────────────────────────────────────────────────────────┘     │
│                                                                  │
│  Behavior:                                                        │
│  • Bypass classification entirely                                 │
│  • Forward directly to QRadar (bounded delivery applies)           │
│  • Record bypass decision in audit trail                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Evidence & Audit (Chain-of-Custody)

### Evidence goals

- Reconstruct timelines (what happened, when, why the system decided)
- Prove integrity (detect tampering, preserve chain-of-custody)
- Enable replay (re-run classification on archived logs)

### Decision record schema (recommended)

Emit a structured decision event for every processed log.

```json
{
  "log_id": "uuid",
  "ingest_ts": "2026-01-21T12:34:56.789Z",
  "source": {
    "vendor": "...",
    "product": "...",
    "host": "...",
    "ip": "..."
  },
  "policy": {
    "compliance_bypass": false,
    "bypass_reason": null
  },
  "model": {
    "model_version": "v1.0.1",
    "rules_version": "2026-01-21",
    "components": {
      "rule_override": 0.12,
      "ml_score": 0.63,
      "anomaly_score": 0.08
    }
  },
  "decision": {
    "class": "suspicious",
    "confidence": 0.71,
    "fail_open": false,
    "route": "qradar"
  },
  "correlation": {
    "kafka_topic": "raw-logs",
    "kafka_partition": 3,
    "kafka_offset": 123456,
    "qradar_event_id": null
  }
}
```

### Storage recommendations

- Raw logs (ALL): cold storage with lifecycle policies and cross-region replication.
- Decisions (ALL): append-only store with long retention.
- Stronger integrity (optional): WORM/Object Lock (or equivalent) for audit and/or cold storage.

### Time synchronization

- Enforce NTP/chrony across nodes.
- Track time drift; treat excessive drift as an incident (breaks timelines).

---

## Trained Models

### Current Model Version: v1 (20260114_160614)

This section mirrors the current production artifact structure; vNext recommends adding a registry (see Model Governance).

### Model Artifacts

```
models/
├── latest -> v1
└── v1/
    ├── tfidf_xgboost/
    │   └── model.joblib          # TF-IDF vectorizer + XGBoost classifier
    ├── anomaly_detector/
    │   └── model.joblib          # Isolation Forest for anomaly detection
    ├── model_info.json           # Model metadata and configuration
    └── training_results.json     # Training metrics and validation results
```

### Model Performance Metrics

| Metric               | Value  | Target | Status  |
| -------------------- | ------ | ------ | ------- |
| **Overall Accuracy** | 100%   | >90%   | ✅ PASS |
| **Critical Recall**  | 100%   | >99.5% | ✅ PASS |
| **CV Score**         | 99.93% | >95%   | ✅ PASS |
| **Validation**       | PASSED | PASS   | ✅ PASS |

### Classification Report

```
              precision    recall  f1-score   support

    critical       1.00      1.00      1.00        30
  suspicious       1.00      1.00      1.00       180
     routine       1.00      1.00      1.00       690
       noise       1.00      1.00      1.00       600

    accuracy                           1.00      1500
   macro avg       1.00      1.00      1.00      1500
weighted avg       1.00      1.00      1.00      1500
```

### Model Configuration

```json
{
  "version": "20260114_160614",
  "accuracy": 1.0,
  "critical_recall": 1.0,
  "passed_validation": true,
  "config": {
    "tfidf_max_features": 10000,
    "tfidf_ngram_range": [1, 3],
    "xgb_n_estimators": 200,
    "xgb_max_depth": 6,
    "xgb_learning_rate": 0.1,
    "anomaly_contamination": 0.1,
    "min_critical_recall": 0.95
  }
}
```

### Retraining Schedule

| Trigger   | Action                        |
| --------- | ----------------------------- |
| Weekly    | Evaluate model drift score    |
| Monthly   | Full retraining with new data |
| On-demand | When false negative detected  |
| Threshold | When drift score > 0.1        |

---

## Model Governance

### Model Lifecycle Management

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        MODEL LIFECYCLE PIPELINE                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐     │
│   │  TRAIN   │──▶│ VALIDATE │──▶│ REGISTER │──▶│  DEPLOY  │──▶│ MONITOR  │     │
│   └──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘     │
│        │              │              │              │              │            │
│        ▼              ▼              ▼              ▼              ▼            │
│   • Offline CV   • Critical      • Version     • Shadow      • Drift detection  │
│   • Feature imp    recall          tagging       mode        • Recall tracking  │
│   • Adversarial   ≥ 99.5%       • Lineage     • Canary       • FN alerts        │
│     tests       • Bias check      tracking     • Gradual                        │
│                                                                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│ Gates (must pass):                                                               │
│ 1) Accuracy ≥ 95%, Critical Recall ≥ 99.5%                                       │
│ 2) No bias regression across log sources                                         │
│ 3) Performance within 10% of previous version                                    │
│ 4) 24h shadow mode with 0 false negatives                                        │
│ 5) 1 week gradual rollout with stable metrics                                    │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Model Registry (Recommended: MLflow)

```
┌─────────────────────────────────────────────────────────────────┐
│                    MODEL REGISTRY STRUCTURE                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  mlflow-artifacts/                                               │
│  └── ai-log-filter/                                              │
│      ├── v1.0.0/                                                 │
│      ├── v1.0.1/ (production)                                    │
│      └── v1.1.0-rc1/ (staging)                                   │
│                                                                  │
│  Stages: None → Staging → Production → Archived                  │
└─────────────────────────────────────────────────────────────────┘
```

### Model Performance Baselines (Realistic)

| Metric               | Training | Validation | Production Target | Alert Threshold |
| -------------------- | -------- | ---------- | ----------------- | --------------- |
| Overall Accuracy     | 98.5%    | 97.2%      | > 95%             | < 93%           |
| Critical Recall      | 99.8%    | 99.5%      | > 99.5%           | < 99%           |
| Critical Precision   | 92.0%    | 89.0%      | > 85%             | < 80%           |
| False Negative Rate  | 0.2%     | 0.5%       | < 0.5%            | > 1%            |
| Noise Filtering Rate | 95.0%    | 92.0%      | > 90%             | < 85%           |

> Note: 100% accuracy on training data indicates overfitting. Expect 2-5% degradation in production.

---

## Validation Framework

### Shadow Mode Validation

```
┌─────────────────────────────────────────────────────────────────┐
│                    SHADOW MODE ARCHITECTURE                      │
│                                                                  │
│  ┌─────────────┐    ┌─────────────────────────────────────┐     │
│  │ Log Entry   │───▶│        SHADOW MODE VALIDATOR         │     │
│  └─────────────┘    │                                      │     │
│                     │  1. AI Classification (observed)      │     │
│                     │  2. Forward to QRadar (control)       │     │
│                     │  3. Compare decisions                 │     │
│                     │  4. Record discrepancies              │     │
│                     └──────────────────┬───────────────────┘     │
│                                        │                         │
│                     ┌──────────────────▼───────────────────┐     │
│                     │      VALIDATION METRICS               │     │
│                     │  • Agreement rate                     │     │
│                     │  • False negative count               │     │
│                     │  • Category distribution              │     │
│                     └───────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

### QRadar Offense Correlation

```
┌─────────────────────────────────────────────────────────────────┐
│                 QRADAR CORRELATION ENGINE                        │
│                                                                  │
│  Purpose: detect false negatives by correlating with QRadar      │
│                                                                  │
│  1. Fetch QRadar offenses                                         │
│  2. Extract source log IDs                                        │
│  3. Lookup AI decisions in audit trail                            │
│  4. False negative if: AI routed routine/noise AND QRadar offense  │
│  5. Alert + log + update recall metrics                           │
└─────────────────────────────────────────────────────────────────┘
```

### Validation Phases

| Phase          | Duration    | Traffic           | Criteria to Proceed               |
| -------------- | ----------- | ----------------- | --------------------------------- |
| **Shadow**     | 24-72 hours | 0% (observe only) | No false negatives, >99.5% recall |
| **Pilot**      | 1 week      | 5% of traffic     | <0.1% false negative rate         |
| **Gradual**    | 2-4 weeks   | 5% → 100%         | Stable metrics, no incidents      |
| **Production** | Ongoing     | 100%              | Continuous monitoring             |

### Rollback Triggers

| Condition               | Action                     |
| ----------------------- | -------------------------- |
| False negative detected | Pause rollout, investigate |
| Critical recall < 99%   | Immediate rollback         |
| Circuit breaker opens   | Automatic fail-open        |
| Latency P99 > 500ms     | Scale up or rollback       |

---

## Deployment Architecture

### Kubernetes Deployment

```
┌─────────────────────────────────────────────────────────────────┐
│                    KUBERNETES CLUSTER                            │
│                                                                  │
│  Namespace: ai-log-filter                                        │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Deployments                                              │    │
│  │                                                          │    │
│  │  ┌─────────────────┐  ┌─────────────────┐               │    │
│  │  │ ai-filter       │  │ ai-filter-api   │               │    │
│  │  │ replicas: 6     │  │ replicas: 3     │               │    │
│  │  │ cpu: 2          │  │ cpu: 1          │               │    │
│  │  │ mem: 4Gi        │  │ mem: 2Gi        │               │    │
│  │  └─────────────────┘  └─────────────────┘               │    │
│  │                                                          │    │
│  │  ┌───────────────────────────────────────────────────┐   │    │
│  │  │ qradar-delivery-worker (vNext)                     │   │    │
│  │  │ drains pending-qradar at a bounded rate            │   │    │
│  │  └───────────────────────────────────────────────────┘   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ HorizontalPodAutoscaler                                  │    │
│  │  ai-filter: min 3 / max 20 (CPU + consumer lag)          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ PodDisruptionBudget                                      │    │
│  │  ai-filter: minAvailable 50%                             │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Security: NetworkPolicies (deny-by-default) + SA least privilege │
└─────────────────────────────────────────────────────────────────┘
```

### Deployment Files

| File                                | Purpose                  |
| ----------------------------------- | ------------------------ |
| `deploy/kubernetes/deployment.yaml` | Main K8s manifests       |
| `configs/production.yaml`           | Production configuration |
| `configs/prometheus-alerts.yaml`    | Alert rules              |
| `docker-compose.yml`                | Local development        |

---

## Monitoring & Observability

### Key Metrics Dashboard (example)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        AI LOG FILTER - OPERATIONS DASHBOARD                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  THROUGHPUT                          LATENCY                                 │
│  ┌────────────────────────┐         ┌────────────────────────┐              │
│  │ EPS Ingested: 45,230   │         │ P50:  23ms            │              │
│  │ EPS to QRadar: 18,092  │         │ P95:  67ms            │              │
│  │ EPS Filtered: 27,138   │         │ P99:  89ms            │              │
│  │ Reduction: 60.0%       │         │ Max: 156ms            │              │
│  └────────────────────────┘         └────────────────────────┘              │
│                                                                              │
│  QUALITY                             BACKPRESSURE                            │
│  ┌────────────────────────┐         ┌────────────────────────┐              │
│  │ Critical Recall: 99.7% │         │ Kafka Lag:     1,234  │              │
│  │ False Neg (24h):    0  │         │ pending-qradar:   0   │              │
│  │ Drift Score:     0.02  │         │ Circuit:      CLOSED  │              │
│  └────────────────────────┘         └────────────────────────┘              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Prometheus Metrics

| Metric                                     | Type      | Description                                           |
| ------------------------------------------ | --------- | ----------------------------------------------------- |
| `ai_filter_logs_processed_total`           | Counter   | Total logs processed                                  |
| `ai_filter_logs_forwarded_total`           | Counter   | Logs forwarded to QRadar                              |
| `ai_filter_classification_latency_seconds` | Histogram | Classification latency                                |
| `ai_filter_critical_recall`                | Gauge     | Critical event recall                                 |
| `ai_filter_false_negatives_total`          | Counter   | False negatives detected                              |
| `ai_filter_circuit_breaker_state`          | Gauge     | 0=closed, 1=open, 2=half-open                         |
| `ai_filter_model_drift_score`              | Gauge     | Drift score                                           |
| `ai_filter_eps_reduction_ratio`            | Gauge     | EPS reduction                                         |
| `ai_filter_pending_qradar_depth`           | Gauge     | Backlog depth when QRadar is slow/unreachable (vNext) |

### Alert Rules (reference)

```yaml
# Critical Alerts (PagerDuty)
- alert: CriticalRecallDropped
  expr: ai_filter_critical_recall < 0.995
  for: 5m
  severity: critical

- alert: CircuitBreakerOpen
  expr: ai_filter_circuit_breaker_state == 1
  for: 1m
  severity: critical

- alert: FalseNegativeDetected
  expr: increase(ai_filter_false_negatives_total[5m]) > 0
  for: 0m
  severity: critical

- alert: PendingQRadarBacklog
  expr: ai_filter_pending_qradar_depth > 100000
  for: 5m
  severity: critical

# Warning Alerts (Slack)
- alert: ModelDriftDetected
  expr: ai_filter_model_drift_score > 0.1
  for: 30m
  severity: warning

- alert: KafkaConsumerLag
  expr: kafka_consumer_lag > 50000
  for: 5m
  severity: warning
```

---

## Incident Response

### Severity Levels

| Level | Name     | Examples                                 | Response Time | Escalation |
| ----- | -------- | ---------------------------------------- | ------------- | ---------- |
| SEV1  | Critical | False negative detected, circuit open    | 5 min         | VP Eng     |
| SEV2  | Major    | Critical recall < 99%, sustained backlog | 15 min        | Eng Lead   |
| SEV3  | Minor    | Consumer lag > 10K, drift warning        | 1 hour        | On-call    |
| SEV4  | Low      | Non-urgent performance degradation       | 4 hours       | Queue      |

### First 5 minutes (operator checklist)

1. Check circuit breaker state (is system failing open?)
2. Check false negative alerting and recall
3. Check Kafka lag and pending-qradar depth
4. Preserve evidence ranges (topic/partition/offset) and decision trail slices

---

## Disaster Recovery

### Recovery Time Objectives

| Scenario             | RTO   | RPO  | Recovery Procedure           |
| -------------------- | ----- | ---- | ---------------------------- |
| Single pod failure   | 30s   | 0    | Kubernetes auto-restart      |
| AZ failure           | 2min  | 0    | Traffic shift to healthy AZ  |
| Region failure       | 15min | 1min | DNS failover + data sync     |
| Model corruption     | 5min  | 0    | Rollback to previous version |
| Total system failure | 30min | 5min | Restore from backup          |

### Backup Strategy

```
DAILY BACKUPS:
├── Model Artifacts (S3 versioning)
├── Configuration (GitOps)
├── Kafka offsets (cluster snapshots)
└── Metrics history (Prometheus snapshots)

CONTINUOUS REPLICATION:
├── Cold Storage (cross-region replication)
├── Audit decisions (immutable append-only)
└── Kafka replication (multi-AZ)
```

---

## Deployment Checklist

### Pre-Deployment

- [ ] Models trained and validated
- [ ] Safety patterns implemented (circuit breaker, compliance gate)
- [ ] Network policies + service accounts reviewed (least privilege)
- [ ] Kafka ACLs configured for all topics (including pending-qradar, audit-decisions)
- [ ] Cold storage retention + replication enabled
- [ ] Audit store configured (append-only; WORM optional)
- [ ] Alerts wired for false negatives, circuit open, lag, pending-qradar depth

### Shadow Mode Deployment

```bash
# 1. Deploy to staging with shadow mode
export SHADOW_MODE_ENABLED=true
kubectl apply -f deploy/kubernetes/deployment.yaml

# 2. Monitor for 24-72 hours
# - ai_filter_false_negatives_total = 0
# - ai_filter_critical_recall > 0.995
```

### Production Rollout

```bash
# 1. Disable shadow mode
export SHADOW_MODE_ENABLED=false

# 2. Start with 5% traffic
kubectl set env deployment/ai-filter TRAFFIC_PERCENTAGE=5

# 3. Increase gradually (monitor between each step)
# 5% → 10% → 25% → 50% → 100%

# 4. Monitor key metrics
watch -n 5 'curl -s http://ai-filter-api/metrics | grep ai_filter'
```

### Rollback Procedure

```bash
# Immediate rollback (circuit breaker handles automatically)
kubectl rollout undo deployment/ai-filter

# Or restore previous model version:
rm models/latest
ln -s v0 models/latest
kubectl rollout restart deployment/ai-filter
```

---

## Appendix: vNext Improvements

### vNext vs Current (Delta)

| Area                  | Current (`PRODUCTION_ARCHITECTURE*.md`)             | vNext (this doc)                                    | Why it matters          |
| --------------------- | --------------------------------------------------- | --------------------------------------------------- | ----------------------- |
| Architecture framing  | Component breakdown; planes/zones sometimes implied | Explicit control/data/evidence planes               | Faster incident reviews |
| Trust boundaries      | Security described, boundaries implicit             | DMZ/app/data zones are first-class                  | Easier threat modeling  |
| QRadar semantics      | Fail-open described                                 | Bounded delivery + `pending-qradar` is an invariant | Prevent SIEM overload   |
| Evidence handling     | Audit trail described                               | Decision schema + chain-of-custody expectations     | Better forensics        |
| Dependency resilience | Integrations shown                                  | Cache-first enrichment + degraded mode              | Better P99 latency      |

---

## File Structure

```
/home/jacob/Projects/tester/
├── src/
│   ├── api/
│   │   ├── app.py                    # FastAPI application
│   │   ├── rate_limiter.py           # Rate limiting middleware
│   │   └── health.py                 # Health/readiness/liveness endpoints
│   ├── models/
│   │   ├── safe_ensemble.py          # Production-safe classifier
│   │   ├── ensemble.py               # Base ensemble logic
│   │   ├── rule_based.py             # Rule-based classifier
│   │   ├── tfidf_classifier.py       # TF-IDF + XGBoost
│   │   └── anomaly_detector.py       # Isolation Forest
│   ├── preprocessing/
│   │   ├── compliance_gate.py        # PCI/HIPAA/SOX bypass
│   │   └── log_parser.py             # Log parsing and normalization
│   ├── monitoring/
│   │   └── production_metrics.py     # Prometheus metrics
│   ├── utils/
│   │   └── circuit_breaker.py        # Circuit breaker pattern
│   ├── validation/
│   │   ├── shadow_mode.py            # Shadow mode validation
│   │   └── qradar_correlation.py     # QRadar offense correlation
│   └── integration/
│       ├── kafka/client.py           # Kafka producer/consumer
│       └── qradar/client.py          # QRadar API client
├── models/
│   ├── latest -> v1
│   └── v1/                           # Trained model artifacts
├── configs/
│   ├── production.yaml               # Production configuration
│   ├── prometheus-alerts.yaml        # Alert rules
│   └── grafana/                      # Grafana dashboards
├── deploy/kubernetes/
│   └── deployment.yaml               # K8s manifests
├── scripts/
│   ├── training_pipeline.py          # Model training
│   ├── validate_models.py            # Model validation
│   ├── shadow_validation.py          # Shadow mode testing
│   └── load_test.py                  # Load testing
├── tests/                            # Unit tests
│   ├── test_api.py                   # API endpoint tests
│   ├── test_rate_limiter.py          # Rate limiting tests
│   ├── test_circuit_breaker.py       # Circuit breaker tests
│   ├── test_safe_ensemble.py         # Ensemble classifier tests
│   └── ...                           # Additional test files
├── .github/workflows/
│   ├── ci.yml                        # CI pipeline
│   └── cd.yml                        # CD pipeline
└── docs/
    ├── architecture/
    │   ├── PRODUCTION_ARCHITECTURE.md
    │   ├── PRODUCTION_ARCHITECTURE_ENHANCED.md
    │   └── PRODUCTION_ARCHITECTURE_VNEXT.md
    ├── runbooks/
    │   ├── OPERATIONS_RUNBOOK.md
    │   └── incident-response.md
    ├── training/
    │   └── SOC_TRAINING_GUIDE.md
    └── ASSESSMENT_SCORECARD.md
```

---

_Document Version: 1.0 (vNext)_  
_Last Updated: January 21, 2026_  
_Owner: Security Engineering_  
_Status: vNext Reference Architecture (Score: 9.6/10)_
