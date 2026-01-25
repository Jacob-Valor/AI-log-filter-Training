# Incident Response Runbook

## Table of Contents

1. [Overview](#overview)
2. [Severity Levels](#severity-levels)
3. [Common Incidents](#common-incidents)
4. [Response Procedures](#response-procedures)
5. [Escalation](#escalation)
6. [Recovery](#recovery)
7. [Post-Incident](#post-incident)

---

## Overview

This runbook provides procedures for responding to incidents affecting the AI Log Filter service. The service is critical for SIEM operations - any outage or degradation impacts security monitoring.

### Service Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  LOG SOURCES │────▶│  AI LOG FILTER│───▶│   QRADAR     │
│  (Kafka)     │     │  (This)      │     │   (SIEM)     │
└──────────────┘     └──────────────┘     └──────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │  Cold Storage│
                     │  (S3)        │
                     └──────────────┘
```

### Key Contacts

| Role              | Contact          | Availability   |
| ----------------- | ---------------- | -------------- |
| Primary On-Call   | @security-oncall | 24/7           |
| Secondary On-Call | @security-lead   | Business Hours |
| Platform Team     | #platform-ops    | Business Hours |
| Security Team     | #security-ops    | 24/7           |

---

## Severity Levels

| Severity            | Description                                      | Response Time | Examples                                   |
| ------------------- | ------------------------------------------------ | ------------- | ------------------------------------------ |
| **SEV1 - Critical** | Complete service outage; no logs reaching QRadar | 15 minutes    | All classifiers down, circuit breaker open |
| **SEV2 - High**     | Major degradation; some logs blocked             | 1 hour        | High latency, partial failures             |
| **SEV3 - Medium**   | Minor degradation; increased noise               | 4 hours       | Metrics spikes, model degradation          |
| **SEV4 - Low**      | Minor issues; no business impact                 | 24 hours      | Logging issues, minor errors               |

---

## Common Incidents

### 🔴 SEV1: Complete Service Outage

**Symptoms:**

- `/health/ready` returns 503
- No logs reaching QRadar
- Circuit breaker is OPEN
- Zero throughput metrics

**Immediate Actions:**

1. **Acknowledge alert** (PagerDuty/Slack)
2. **Check service status:**

```bash
# Check pod status
kubectl get pods -n ai-log-filter

# Check logs
kubectl logs -n ai-log-filter deploy/ai-log-filter --tail=100

# Check health endpoint
curl http://ai-log-filter.example.com/health
```

3. **Check circuit breaker status:**

```bash
# View circuit breaker metrics
curl http://ai-log-filter.example.com/metrics | grep circuit_breaker
```

4. **Common causes & fixes:**

| Cause                | Fix                                |
| -------------------- | ---------------------------------- |
| Kafka unavailable    | Restart Kafka or wait for recovery |
| QRadar API down      | Enable fail-open mode              |
| Model loading failed | Rollback to previous model version |
| OOM crash            | Increase memory limits             |

5. **If circuit breaker is OPEN:**

```bash
# Manual reset (use with caution)
curl -X POST http://ai-log-filter.example.com/admin/circuit-breaker/reset
```

6. **Recovery verification:**

```bash
# Verify health
curl http://ai-log-filter.example.com/health/ready

# Check throughput
curl http://ai-log-filter.example.com/metrics | grep eps_ingested
```

---

### 🟠 SEV2: High Latency / Degraded Performance

**Symptoms:**

- P95 latency > 100ms
- Kafka consumer lag increasing
- Increased error rates

**Diagnostic Steps:**

1. **Check latency metrics:**

```bash
curl http://ai-log-filter.example.com/metrics | grep classification_latency
```

2. **Check Kafka consumer lag:**

```bash
curl http://ai-log-filter.example.com/metrics | grep kafka_consumer_lag
```

3. **Check resource usage:**

```bash
kubectl top pods -n ai-log-filter
```

**Common Causes:**

| Cause           | Solution                                                              |
| --------------- | --------------------------------------------------------------------- |
| High CPU        | Scale horizontally: `kubectl scale deploy/ai-log-filter --replicas=4` |
| Memory pressure | Increase memory limit or enable model unloading                       |
| Slow QRadar API | Increase timeout, enable async mode                                   |
| Network issues  | Check VPC/network metrics                                             |

**Mitigation:**

```bash
# Scale up service
kubectl scale deploy/ai-log-filter -n ai-log-filter --replicas=4

# Restart with fresh resources
kubectl rollout restart deploy/ai-log-filter -n ai-log-filter
```

---

### 🟡 SEV3: Model Degradation

**Symptoms:**

- Increased false positives/negatives
- Accuracy metrics dropping
- Analyst feedback indicating issues

**Diagnostic Steps:**

1. **Check model performance metrics:**

```bash
curl http://ai-log-filter.example.com/metrics | grep model_
```

2. **Review shadow mode validation results:**

```bash
curl http://ai-log-filter.example.com/api/v1/validation/shadow-mode/status
```

3. **Check for model drift:**

```bash
curl http://ai-log-filter.example.com/api/v1/model/drift
```

**Response:**

1. **Enable shadow mode** (if not already):

```bash
curl -X POST http://ai-log-filter.example.com/api/v1/validation/shadow-mode/enable
```

2. **Retrain models:**

```bash
make train MODEL_TYPE=ensemble
make export MODEL_VERSION=new_version
```

3. **Deploy new model version:**

```bash
# Validate new model
python scripts/validate_models.py

# Deploy (requires approval)
# Update models/latest symlink to new version
```

---

### 🟢 SEV4: Minor Issues

**Symptoms:**

- Increased warning logs
- Non-critical metrics spikes
- Test failures

**Response:**

- Monitor for 24 hours
- Create backlog ticket
- Fix in next sprint

---

## Response Procedures

### Standard Incident Response Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        INCIDENT RESPONSE                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. DETECT          2. TRIAGE          3. RESPOND               │
│  ┌─────────┐        ┌─────────┐       ┌─────────┐              │
│  │ Alert   │──────▶│ Assess  │──────▶│ Contain │              │
│  │ Received│        │ Severity│       │ Impact  │              │
│  └─────────┘        └─────────┘       └─────────┘              │
│       │                                    │                   │
│       ▼                                    ▼                   │
│  4. RESOLVE          5. RECOVER          6. LEARN               │
│  ┌─────────┐        ┌─────────┐       ┌─────────┐              │
│  │ Fix    │──────▶│ Verify  │──────▶│ Document│              │
│  │ Issue  │        │ Service │       │ Lessons │              │
│  └─────────┘        └─────────┘       └─────────┘              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Communication Templates

#### Initial Notification

```
🚨 INCIDENT: [Title]
Severity: SEV[1-4]
Status: Investigating
Description: [Brief description]

Current Impact: [What is affected]
Started: [Time]
Owner: [On-call engineer]

Next Update: [Time + 15 min]
Join Incident Channel: #incident-[number]
```

#### Status Update

```
📊 INCIDENT UPDATE: [Title]
Status: [Investigating / Identified / Mitigating / Resolved]
Progress: [What we've done so far]

Current State: [What is happening now]
Next Action: [What we're doing next]

ETA for Resolution: [Time or "Unknown"]
```

#### Resolution

```
✅ INCIDENT RESOLVED: [Title]
Duration: [Start time] - [End time]
Total Time: [X hours Y minutes]

Summary: [What happened and why]
Resolution: [What fixed it]
Lessons: [Key takeaways]
```

---

## Escalation

### Escalation Path

```
SEV1: On-call (15min) → Security Lead (30min) → CTO (1hr)
SEV2: On-call (1hr) → Security Lead (2hr) → Platform Lead (4hr)
SEV3: On-call (4hr) → Team Lead (next day)
SEV4: Next business day
```

### Escalation Triggers

- **Time-based:** Response not meeting SLA
- **Impact-based:** Incident spreading or worsening
- **Technical:** Need expertise not available

### Escalation Command

```bash
# Trigger escalation in PagerDuty
# Or notify in Slack:
/incident escalate @security-lead
```

---

## Recovery

### Recovery Checklist

- [ ] Service health check passes (`/health/ready`)
- [ ] Throughput metrics return to normal
- [ ] Latency within SLA (<50ms P95)
- [ ] No circuit breaker activations
- [ ] Kafka consumer lag resolved
- [ ] QRadar receiving events
- [ ] No new alerts for 30 minutes
- [ ] Stakeholders notified

### Rollback Procedure

If recent deployment caused issue:

```bash
# 1. Identify previous version
git log --oneline -5

# 2. Revert deployment
git revert HEAD
git push origin main

# 3. Or rollback Docker image
kubectl set image deploy/ai-log-filter ai-log-filter=ghcr.io/org/ai-log-filter:previous-version -n ai-log-filter

# 4. Verify recovery
kubectl rollout status deploy/ai-log-filter -n ai-log-filter
```

---

## Post-Incident

### Required Within 48 Hours

1. **Incident Report** (use template below)
2. **Root Cause Analysis**
3. **Action Items** with owners
4. **Process Improvements**

### Incident Report Template

```markdown
# Incident Report: [Incident Title]

## Summary

- **ID:** INC-[number]
- **Date:** [YYYY-MM-DD]
- **Duration:** [X hours Y minutes]
- **Severity:** SEV[1-4]
- **Owner:** [Name]

## Impact

- [Description of business/technical impact]
- [Number of affected users/systems]
- [Estimated cost of downtime]

## Timeline (All times UTC)

| Time  | Event                 |
| ----- | --------------------- |
| HH:MM | Alert received        |
| HH:MM | Investigation started |
| HH:MM | Root cause identified |
| HH:MM | Fix implemented       |
| HH:MM | Service restored      |

## Root Cause

[Technical explanation of what went wrong]

## Resolution

[What actions resolved the incident]

## Lessons Learned

### What went well

-

### What went poorly

-

### Where we got lucky

-

## Action Items

| ID  | Action | Owner | Due Date |
| --- | ------ | ----- | -------- |
|     |        |       |          |
```

---

## Useful Commands

### Service Management

```bash
# Restart service
kubectl rollout restart deploy/ai-log-filter -n ai-log-filter

# Scale service
kubectl scale deploy/ai-log-filter -n ai-log-filter --replicas=4

# View events
kubectl get events -n ai-log-filter --sort-by='.lastTimestamp'

# Check config
kubectl get cm ai-log-filter-config -n ai-log-filter -o yaml
```

### Metrics & Monitoring

```bash
# View all metrics
curl http://ai-log-filter.example.com/metrics

# View specific metric
curl http://ai-log-filter.example.com/metrics | grep classification_latency

# Check health
curl http://ai-log-filter.example.com/health
```

### Log Analysis

```bash
# View recent logs
kubectl logs -n ai-log-filter deploy/ai-log-filter --tail=500

# Follow logs
kubectl logs -n ai-log-filter deploy/ai-log-filter -f

# Search for errors
kubectl logs -n ai-log-filter deploy/ai-log-filter | grep -i error
```

---

## Appendix

### Key Metrics Thresholds

| Metric                     | Warning | Critical |
| -------------------------- | ------- | -------- |
| Classification Latency P95 | >50ms   | >100ms   |
| Kafka Consumer Lag         | >1000   | >10000   |
| Circuit Breaker Open       | N/A     | Any      |
| EPS (Events Per Second)    | <5000   | <1000    |
| Critical Recall            | <0.99   | <0.95    |

### Related Documentation

- [Architecture Overview](../architecture.md)
- [Runbook: Model Deployment](../model-deployment.md)
- [Runbook: QRadar Integration](../qradar-integration.md)
- [Post-Incident Template](templates/post-incident.md)
