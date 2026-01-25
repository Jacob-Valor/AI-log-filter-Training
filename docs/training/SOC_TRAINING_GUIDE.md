# AI Log Filter - SOC Training Guide

## Security Operations Center Training Materials

**Version:** 1.0  
**Last Updated:** January 2026  
**Audience:** SOC Analysts and Engineers

---

## Table of Contents

1. [Overview](#1-overview)
2. [System Architecture](#2-system-architecture)
3. [Daily Operations](#3-daily-operations)
4. [Alert Triage](#4-alert-triage)
5. [Incident Response](#5-incident-response)
6. [Troubleshooting](#6-troubleshooting)
7. [FAQ](#7-faq)
8. [Quick Reference](#8-quick-reference)

---

## 1. Overview

### What is AI Log Filter?

The AI Log Filter is an intelligent pre-processing system that sits between your log sources and QRadar SIEM. Its primary purpose is to:

- **Reduce noise** by filtering out routine and low-value logs (target: 40-60% reduction)
- **Prioritize alerts** by classifying logs into critical, suspicious, routine, and noise
- **Preserve compliance** by ensuring regulated logs (PCI-DSS, HIPAA, SOX, GDPR) bypass AI filtering
- **Prevent data loss** with fail-open design - all errors result in logs being sent to QRadar

### Key Design Principles

| Principle            | Implementation                                |
| -------------------- | --------------------------------------------- |
| **Fail-Open**        | If AI fails, all logs → QRadar (no data loss) |
| **Compliance First** | Regulated logs bypass AI entirely             |
| **Zero Trust**       | Every classification logged with explanation  |
| **Observability**    | Full metrics, traces, and audit trails        |

### Expected Benefits

| Metric                 | Target |
| ---------------------- | ------ |
| EPS Reduction          | 40-60% |
| Analyst Time Saved     | 30-50% |
| Critical Recall        | >99.5% |
| License Cost Reduction | 25-40% |

---

## 2. System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              LOG SOURCES                                     │
│  Firewall  │  IDS/IPS  │  Endpoint  │  Application  │  Network  │  Cloud   │
└────────────┴───────────┴────────────┴───────────────┴───────────┴──────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AI LOG FILTER                                      │
│  ┌─────────────┐     ┌─────────────────┐     ┌─────────────────────────┐   │
│  │   KAFKA     │────▶│  AI CLASSIFIER  │────▶│     QRADAR SIEM         │   │
│  │  Consumer   │     │  (ML + Rules)   │     │                         │   │
│  └─────────────┘     └─────────────────┘     └─────────────────────────┘   │
│                              │                               │               │
│                              │                               │               │
│                              ▼                               ▼               │
│                       ┌─────────────┐              ┌─────────────────┐      │
│                       │  COLD       │              │   COMPLIANCE     │      │
│                       │  STORAGE    │              │   BYPASS         │      │
│                       │  (S3)       │              │   (PCI, HIPAA)   │      │
│                       └─────────────┘              └─────────────────┘      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Classification Categories

| Category       | Description                                    | Destination              | Examples                                                 |
| -------------- | ---------------------------------------------- | ------------------------ | -------------------------------------------------------- |
| **Critical**   | Security threats requiring immediate attention | QRadar (High Priority)   | Failed logins, malware, SQL injection, data exfiltration |
| **Suspicious** | Potentially malicious activity                 | QRadar (Medium Priority) | Unusual access times, port scans, failed 2FA             |
| **Routine**    | Normal operational activity                    | Filtered (archived)      | Successful logins, file access, API calls                |
| **Noise**      | Low-value housekeeping logs                    | Filtered (archived)      | Heartbeats, health checks, debug traces                  |

### Compliance Bypass

The following regulated log types **bypass AI filtering entirely** and go directly to QRadar:

| Regulation  | Triggers                                 | Retention    |
| ----------- | ---------------------------------------- | ------------ |
| **PCI-DSS** | `pci_*`, `payment_*`, `cardholder_*`     | 365 days     |
| **HIPAA**   | `hipaa_*`, `ehr_*`, `patient_*`, `phi_*` | 6 years      |
| **SOX**     | `financial_*`, `trading_*`, `audit_*`    | 7 years      |
| **GDPR**    | `gdpr_*`, `pii_*`                        | Configurable |

---

## 3. Daily Operations

### Morning Checklist (5 minutes)

```markdown
1. ✅ Check Grafana Dashboard
   - Verify EPS reduction is in 40-60% range
   - Confirm Critical Recall > 99.5%
   - Check P99 latency < 100ms

2. ✅ Review Alert Volume
   - Compare to baseline
   - Investigate significant spikes

3. ✅ Verify System Health
   - Check circuit breaker status (should be CLOSED)
   - Confirm no errors in logs
```

### Accessing Monitoring

**Grafana Dashboard:**

```
URL: http://ai-log-filter.example.com/grafana
User: Provided by platform team
```

**Key Metrics to Monitor:**

| Metric          | Normal Range | Alert Threshold |
| --------------- | ------------ | --------------- |
| EPS Reduction   | 40-60%       | <30% or >70%    |
| Critical Recall | >99.5%       | <99%            |
| P99 Latency     | <100ms       | >200ms          |
| Circuit Breaker | CLOSED       | OPEN            |
| Error Rate      | <0.1%        | >1%             |

### Common Daily Tasks

#### Task 1: Review False Negatives

If the system flagged a critical event as "routine" or "noise":

1. Check QRadar for the missed event
2. Document the event pattern
3. Submit to ML team for model improvement

#### Task 2: Handle Compliance Alerts

Regulated logs bypass AI - no action needed unless:

- False positive in bypass rules
- New regulation requirements

#### Task 3: Address Performance Issues

If latency increases or errors spike:

1. Check Kafka consumer lag
2. Review system resources
3. Escalate to platform team if needed

---

## 4. Alert Triage

### Critical Alerts (Response: Immediate)

Critical alerts require **immediate attention** within 15 minutes.

**Examples:**

- Failed login attempts (potential brute force)
- Malware detection
- SQL injection attempts
- Data exfiltration attempts
- Privilege escalation

**Triage Steps:**

```
1. ACKNOWLEDGE the alert in QRadar
2. VERIFY the threat:
   - Check source IP reputation
   - Review affected user account
   - Check for related events
3. CONTAIN if confirmed:
   - Block source IP if needed
   - Disable compromised account
4. ESCALATE per incident response plan
5. DOCUMENT all actions
```

### Suspicious Alerts (Response: Within 1 hour)

Suspicious alerts need investigation but are less urgent.

**Examples:**

- Unusual access times
- Multiple failed authentications
- Port scanning activity
- Anomalous data access patterns

**Triage Steps:**

```
1. REVIEW the alert details
2. CONTEXTUALIZE:
   - Is this expected behavior?
   - Has the user/account been flagged before?
3. INVESTIGATE:
   - Check related events
   - Review user history
4. DISMISS or ESCALATE based on findings
5. DOCUMENT decision
```

### Routine & Noise (Response: Review periodically)

These are filtered but archived. Review weekly to:

- Ensure filtering is working correctly
- Identify new patterns that should be classified differently

---

## 5. Incident Response

### When AI Log Filter Has an Outage

**Symptoms:**

- No logs reaching QRadar from AI Filter
- Circuit breaker shows OPEN
- High consumer lag in Kafka

**Response (follow incident response runbook):**

```
PHASE 1: DETECT (0-5 minutes)
├── Confirm outage (check Grafana /health endpoint)
├── Check circuit breaker status
└── Notify on-call (PagerDuty #ai-log-filter)

PHASE 2: RESPOND (5-30 minutes)
├── Verify Kafka is operational
├── Check QRadar API availability
├── Attempt circuit breaker reset
└── If persist: Enable fail-open bypass

PHASE 3: ESCALATE (30+ minutes)
├── Escalate to platform team
├── Consider QRadar direct ingestion
└── Document incident

PHASE 4: RECOVERY
├── Verify normal operation
├── Review metrics for data loss
└── Complete post-incident report
```

### False Negative Incident

If a critical threat was missed by AI Filter:

```
1. IMMEDIATE ACTIONS
   ├── Contain the threat manually
   ├── Notify SOC lead
   └── Document the missed detection

2. INVESTIGATION
   ├── Retrieve original log from cold storage (S3)
   ├── Analyze why classification failed
   ├── Check if pattern matches bypass rules

3. REMEDIATION
   ├── Add new rule if needed
   ├── Retrain model if pattern is new
   └── Update bypass rules if misconfigured

4. PREVENTION
   ├── Add pattern to rule-based classifier
   ├── Document in detection gap analysis
   └── Schedule model retraining
```

---

## 6. Troubleshooting

### Common Issues and Solutions

| Issue                    | Symptoms               | Solution                             |
| ------------------------ | ---------------------- | ------------------------------------ |
| **High Latency**         | P99 > 100ms            | Check resources, scale horizontally  |
| **Consumer Lag**         | Lag > 1000             | Increase consumer instances          |
| **Circuit Open**         | All logs bypass AI     | Check model health, reset breaker    |
| **Low Reduction**        | <30% EPS reduction     | Review filtering rules, add patterns |
| **High False Negatives** | Missed critical events | Retrain model, add rules             |

### Diagnostic Commands

```bash
# Check service health
curl http://ai-log-filter:8000/health

# Check circuit breaker
curl http://ai-log-filter:8000/metrics | grep circuit

# View recent errors
kubectl logs -n ai-log-filter -l app=ai-log-filter --tail=100 | grep ERROR

# Check Kafka lag
curl http://ai-log-filter:8000/metrics | grep kafka_consumer_lag

# View classification distribution
curl http://ai-log-filter:8000/metrics | grep classifications_total
```

### Escalation Path

```
Level 1: SOC Analyst
  └── Routine troubleshooting, documentation

Level 2: SOC Lead
  ├── Complex incidents
  ├── Pattern analysis
  └── False negative investigation

Level 3: Platform Team
  ├── Infrastructure issues
  ├── Performance problems
  └── Deployment concerns

Level 4: ML Engineering
  ├── Model retraining
  ├── Algorithm improvements
  └── New model deployment
```

---

## 7. FAQ

**Q: What happens if the AI model fails?**
A: Fail-open design ensures all logs are sent directly to QRadar. No data loss.

**Q: Can I trust the classification?**
A: Yes, with 99.5%+ critical recall. All classifications include confidence scores and explanations.

**Q: What about compliance?**
A: Regulated logs (PCI, HIPAA, SOX, GDPR) bypass AI entirely and go directly to QRadar.

**Q: How do I report a false negative?**
A: Document in the SOC ticketing system with the log content and expected classification.

**Q: Can I override the AI classification?**
A: Yes, analysts can manually reclassify in QRadar. These decisions help improve the model.

**Q: How often is the model retrained?**
A: Monthly, or sooner if significant drift is detected.

---

## 8. Quick Reference

### Key URLs

| Service            | URL                                        |
| ------------------ | ------------------------------------------ |
| Grafana Dashboard  | `http://ai-log-filter.example.com/grafana` |
| Health Check       | `http://ai-log-filter:8000/health`         |
| Prometheus Metrics | `http://ai-log-filter:8000/metrics`        |
| API Documentation  | `http://ai-log-filter:8000/docs`           |

### Key Metrics

| Metric                                     | Description                 | Target     |
| ------------------------------------------ | --------------------------- | ---------- |
| `ai_filter_eps_reduction_ratio`            | % of logs filtered          | 40-60%     |
| `ai_filter_critical_recall`                | % of critical events caught | >99.5%     |
| `ai_filter_classification_latency_seconds` | Processing time             | <100ms     |
| `ai_filter_circuit_breaker_state`          | System health               | 0 (closed) |

### Contact Information

| Role          | Contact               | When           |
| ------------- | --------------------- | -------------- |
| On-Call       | @ai-log-filter-oncall | 24/7           |
| Platform Team | #platform-ops         | Infrastructure |
| ML Team       | #ai-log-filter-ml     | Model issues   |
| SOC Lead      | @soc-lead             | Escalations    |

---

## Training Completion

To complete SOC training:

1. ✅ Read this guide
2. ✅ Complete hands-on exercises (below)
3. ✅ Pass the knowledge check (10 questions, 80% to pass)
4. ✅ Shadow a senior analyst for 1 shift
5. ✅ Get sign-off from SOC Lead

### Hands-On Exercises

**Exercise 1: Dashboard Review (15 min)**

- Navigate to Grafana
- Identify current EPS reduction rate
- Check for any alerts

**Exercise 2: Alert Triage (30 min)**

- Review 5 critical alerts
- Document investigation steps
- Make disposition decisions

**Exercise 3: False Negative Scenario (30 min)**

- Review missed detection
- Document the event
- Propose remediation

**Exercise 4: Incident Drill (45 min)**

- Simulate AI Filter outage
- Follow incident response steps
- Practice escalation

---

## Document Control

| Version | Date     | Author        | Changes         |
| ------- | -------- | ------------- | --------------- |
| 1.0     | Jan 2026 | Security Team | Initial release |

---

**Questions?** Contact the platform team or add to the #ai-log-filter-training channel.
