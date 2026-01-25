# AI Log Filter - Operations Runbook

## Table of Contents

1. [System Overview](#system-overview)
2. [Daily Operations](#daily-operations)
3. [Incident Response Standards](#incident-response-standards)
4. [Incident Response Procedures](#incident-response-procedures)
5. [Troubleshooting Guide](#troubleshooting-guide)
6. [Maintenance Procedures](#maintenance-procedures)
7. [Rollback Procedures](#rollback-procedures)
8. [Contact Information](#contact-information)

---

## System Overview

### Architecture Summary

```
Log Sources → Kafka → AI Filter → Routing
                         ↓
              ┌─────────────────────┐
              │  Critical/Suspicious│ → QRadar
              │  Routine/Noise      │ → Cold Storage
              │  All Logs           │ → Archive (compliance)
              └─────────────────────┘
```

### Key Components

| Component      | Purpose            | Health Endpoint          |
| -------------- | ------------------ | ------------------------ |
| AI Filter      | Log classification | `:8080/health`           |
| Kafka Consumer | Log ingestion      | Consumer lag metric      |
| QRadar Router  | SIEM forwarding    | QRadar connection status |
| Cold Storage   | Log archival       | S3/bucket metrics        |

### Critical Metrics

| Metric                                 | Normal Range | Alert Threshold |
| -------------------------------------- | ------------ | --------------- |
| `ai_filter_critical_recall`            | > 0.995      | < 0.99          |
| `ai_filter_false_negative_rate`        | < 0.001      | > 0.005         |
| `ai_filter_circuit_breaker_state`      | 0 (closed)   | 1 (open)        |
| `kafka_consumer_lag`                   | < 5,000      | > 50,000        |
| `ai_filter_classification_latency_p99` | < 100ms      | > 500ms         |

---

## Daily Operations

### Morning Health Check (9:00 AM)

1. **Check Grafana Dashboard**
   - Verify EPS rates are within normal range
   - Check classification distribution (critical ~2%, suspicious ~12%, routine ~45%, noise ~40%)
   - Verify no circuit breakers are open

2. **Review Overnight Alerts**
   - Check PagerDuty for any triggered alerts
   - Review false negative reports from shadow mode validation

3. **Validate Model Performance**
   ```bash
   curl http://ai-filter:8080/health | jq '.metrics'
   ```

### Weekly Tasks

- [ ] Review false negative reports and adjust rules if needed
- [ ] Check model drift scores
- [ ] Verify cold storage archival is working
- [ ] Review compliance bypass statistics
- [ ] Update threat intel patterns in rules.yaml

---

## Incident Response Standards

### Incident Classification

| Type                    | Examples                                          | Primary Owner         |
| ----------------------- | ------------------------------------------------- | --------------------- |
| Security breach         | Credential compromise, malware, data exfiltration | Security Ops          |
| Service outage          | API down, failed deployment, cluster outage       | Platform Ops          |
| Performance degradation | High latency, Kafka lag, resource exhaustion      | Platform Ops          |
| Data incident           | Log loss risk, cold storage failure, corruption   | Security + Data       |
| Compliance violation    | Regulated logs filtered, retention issues         | Security + Compliance |
| Third-party failure     | QRadar down, threat intel feed outage             | Platform Ops          |
| Natural disaster        | Region loss, AZ outage                            | Incident Commander    |
| Human error             | Misconfig, accidental deletion                    | Owning Team           |

### Severity Matrix & SLAs

| Severity | Definition                                        | Response SLA     | Update Cadence | Escalations              |
| -------- | ------------------------------------------------- | ---------------- | -------------- | ------------------------ |
| SEV1     | Active breach, full outage, or data loss risk     | < 5 min          | Every 15 min   | Exec + Legal + Security  |
| SEV2     | Partial outage, detection gap, QRadar unreachable | < 15 min         | Every 30 min   | Security Lead + Platform |
| SEV3     | Performance degradation or false positive spike   | < 1 hr           | Every 2 hrs    | On-call + Team Lead      |
| SEV4     | Minor issue, no user impact                       | < 1 business day | Daily          | Team Lead                |

### First Response Checklist

- [ ] Initial assessment and severity determination
- [ ] Assign Incident Commander, Ops Lead, Security Lead, and Scribe
- [ ] Identify affected systems, scope, and customer impact
- [ ] Contain impact (service isolation, access revocation, traffic blocking)
- [ ] Preserve evidence (logs, snapshots, configs, memory, network captures)
- [ ] Start timeline and decision log
- [ ] Initiate communications and stakeholder updates
- [ ] Define recovery plan, rollback criteria, and validation steps

### Evidence Preservation & Chain of Custody

- Preserve raw logs and snapshots before making changes
- Capture system state (configs, memory dumps, network flows) when relevant
- Store evidence in immutable storage with restricted access
- Record hashes and access events for every artifact

| Evidence ID      | Source             | Collector | Time (UTC)           | Hash       | Storage Location   | Access Log  | Notes           |
| ---------------- | ------------------ | --------- | -------------------- | ---------- | ------------------ | ----------- | --------------- |
| EVT-YYYYMMDD-001 | Kafka topic / host | Name      | 2026-01-15T12:00:00Z | sha256:... | s3://forensics/... | ticket link | initial capture |

### Communication Protocol

- Incident Commander owns status cadence and decision approvals
- Security Lead coordinates breach/compliance communications and evidence
- Platform Lead coordinates mitigation, rollback, and recovery
- Scribe maintains timeline, action log, and comms record
- Update cadence: SEV1 every 15 min, SEV2 every 30 min, SEV3 every 2 hours
- External messaging requires Security + Legal review before release

### Recovery Verification

- [ ] QRadar receiving critical/suspicious logs
- [ ] Cold storage writes healthy and backlogs drained
- [ ] Circuit breaker closed and fail-open events normal
- [ ] Critical recall, latency, and Kafka lag within targets
- [ ] Stakeholder communications completed and recorded

### Documentation & Post-Incident

- Maintain incident report with timeline, evidence catalog, decisions, and root cause
- Complete post-incident review within 5 business days
- Track action items to closure and update rules/tests/runbook

### Response Quality Checklist

- [ ] Response time < 5 minutes achieved
- [ ] Classification accuracy > 95% maintained
- [ ] Documentation complete throughout
- [ ] Evidence chain preserved properly
- [ ] Communication SLA met consistently
- [ ] Recovery verified thoroughly
- [ ] Lessons documented systematically
- [ ] Improvements implemented continuously

---

## Incident Response Procedures

### INC-001: Circuit Breaker Open (CRITICAL)

**Symptoms:**

- Alert: "AI Filter Circuit Breaker OPEN"
- All logs being forwarded to QRadar (fail-open mode)
- High QRadar EPS

**Impact:**

- No log filtering - full EPS hitting QRadar
- Potential license cost increase
- No security impact (fail-open ensures all logs reach SIEM)

**Response Steps:**

1. **Acknowledge alert** - This is fail-safe behavior, not a security risk
2. **Check circuit breaker status:**
   ```bash
   kubectl exec -it deploy/ai-log-filter -- curl localhost:8080/health | jq '.components[] | select(.name=="circuit_breakers")'
   ```
3. **Review recent errors:**
   ```bash
   kubectl logs deploy/ai-log-filter --since=10m | grep ERROR
   ```
4. **Common causes:**
   - Model loading failure → Check model volume mount
   - Memory pressure → Check pod resources
   - Kafka connection issues → Check Kafka cluster
5. **Recovery:**
   - Circuit auto-recovers after 30 seconds if underlying issue is resolved
   - For manual reset:
   ```bash
   kubectl exec -it deploy/ai-log-filter -- curl -X POST localhost:8000/api/v1/admin/circuit-breaker/reset
   ```
6. **Post-incident:**
   - Review logs to identify root cause
   - Update runbook if new failure mode discovered

---

### INC-002: False Negative Detected (HIGH)

**Symptoms:**

- Alert: "False Negative Detected"
- QRadar offense generated for log that AI classified as routine/noise

**Impact:**

- Detection delay (log reached QRadar eventually via shadow mode)
- Potential gap in real-time alerting

**Response Steps:**

1. **Get false negative details:**
   ```bash
   curl http://ai-filter:8000/api/v1/validation/missed-offenses | jq '.[0]'
   ```
2. **Analyze the missed log:**
   - What category did AI assign?
   - What was the confidence score?
   - Which model(s) got it wrong?
3. **Immediate mitigation:**
   - If pattern is identifiable, add to critical rules:
   ```yaml
   # configs/rules.yaml - add new rule
   critical:
     - name: "new_threat_pattern"
       patterns:
         - "pattern_from_missed_log"
       confidence: 0.95
   ```
4. **Deploy rule update:**
   ```bash
   kubectl rollout restart deployment/ai-log-filter
   ```
5. **Long-term fix:**
   - Add to training data for next model version
   - Update anomaly detector baseline

---

### INC-003: High Kafka Consumer Lag (MEDIUM)

**Symptoms:**

- Alert: "Kafka Consumer Lag > 50,000"
- Delayed log processing

**Response Steps:**

1. **Check current lag:**
   ```bash
   kubectl exec -it kafka-client -- kafka-consumer-groups.sh \
     --bootstrap-server kafka:9092 \
     --group ai-log-filter-prod \
     --describe
   ```
2. **Scale up consumers:**
   ```bash
   kubectl scale deployment/ai-log-filter --replicas=10
   ```
3. **If lag > 100,000:**
   - Consider activating bypass mode temporarily
   - Forward all logs directly to QRadar
4. **Root cause analysis:**
   - Sudden traffic spike?
   - Model performance degradation?
   - Resource constraints?

---

### INC-004: Model Drift Detected (MEDIUM)

**Symptoms:**

- Alert: "Model Drift Score > 0.1"
- Classification distribution shifting

**Response Steps:**

1. **Check drift metrics:**
   ```bash
   curl http://ai-filter:9090/metrics | grep model_drift
   ```
2. **Compare current vs. baseline distribution:**
   - Is critical % increasing or decreasing?
   - Are new log patterns appearing?
3. **If drift is benign (e.g., new log source added):**
   - Update baseline
   - Continue monitoring
4. **If drift indicates problem:**
   - Check for data quality issues
   - Review recent rule changes
   - Consider model retraining

---

### INC-005: Service Down (CRITICAL)

**Symptoms:**

- Alert: "AI Log Filter service is down"
- Health endpoints failing or pods crash looping
- No metrics emitted

**Impact:**

- Log filtering unavailable
- Potential gap if fail-open/bypass not functioning

**Response Steps:**

1. **Confirm fail-open/bypass status:**
   - Verify logs still reaching QRadar and cold storage
   - Check `ai_filter_fail_open_events_total` for spikes
2. **Check deployment health:**
   ```bash
   kubectl get pods -l app=ai-log-filter
   kubectl describe deployment/ai-log-filter
   ```
3. **Inspect recent logs and events:**
   ```bash
   kubectl logs deploy/ai-log-filter --since=15m
   kubectl get events --sort-by=.lastTimestamp | tail -n 20
   ```
4. **Recover service:**
   - Restart/rollback deployment or scale replicas
   - Validate config/secrets mounts and model volume
5. **Verify recovery:**
   - `curl http://ai-filter:8080/health/ready`
   - Confirm metrics and routing queues stable

---

### INC-006: QRadar Unreachable (HIGH)

**Symptoms:**

- Routing errors for destination `qradar`
- Pending queue growth or retries
- Offense creation delayed

**Impact:**

- Critical/suspicious logs delayed in QRadar
- Detection latency increases

**Response Steps:**

1. **Validate connectivity and credentials:**
   ```bash
   kubectl exec -it deploy/ai-log-filter -- curl -vk https://qradar:443/api/health
   ```
2. **Check routing error metrics/logs:**
   - `ai_filter_routing_errors_total{destination="qradar"}`
3. **Confirm buffering is active:**
   - Monitor `pending-qradar` topic growth
   - Ensure Kafka retention prevents loss
4. **Engage QRadar support and notify stakeholders**
5. **After recovery:**
   - Drain pending queue and validate offense creation

---

### INC-007: Cold Storage Failure (HIGH)

**Symptoms:**

- Routing errors for `cold_storage`
- S3/Blob/GCS errors in logs
- Archive backlog growth

**Impact:**

- Compliance and audit retention at risk
- Potential data loss if buffering overflows

**Response Steps:**

1. **Validate storage endpoint and credentials**
2. **Check routing error metrics/logs:**
   - `ai_filter_routing_errors_total{destination="cold_storage"}`
3. **Ensure buffering is active (Kafka/backlog)**
4. **If outage persists > 30 min:**
   - Enable `BYPASS_MODE=true` to keep logs in QRadar
   - Open compliance incident and notify Security Lead
5. **Backfill archives after storage restored**

---

### INC-008: High False Positive Rate (MEDIUM)

**Symptoms:**

- Alert: "AI Log Filter false positive rate is high"
- Analyst feedback marking many alerts as noise

**Impact:**

- Analyst fatigue and reduced trust in alerts
- Increased QRadar load

**Response Steps:**

1. **Sample false positives and identify patterns**
2. **Tune rules and confidence thresholds**
3. **Add samples to training data for next model**
4. **Monitor alert rates after deployment**

---

### INC-009: Compliance Bypass Spike (MEDIUM)

**Symptoms:**

- Alert: "High percentage of logs bypassing AI due to compliance"
- EPS reduction drops below target

**Impact:**

- Reduced cost savings and processing efficiency
- Possible misclassification of regulated sources

**Response Steps:**

1. **Identify top bypass sources/patterns**
2. **Validate with Compliance before modifying patterns**
3. **Refine bypass regex rules and redeploy**
4. **Monitor bypass ratio and EPS reduction**

---

## Troubleshooting Guide

### Log Classification Issues

#### "Too many logs classified as critical"

1. Check rule patterns - may be too broad
2. Review ML model confidence threshold - may be too low
3. Check for new log source with different format

#### "Too many logs classified as noise"

1. Verify ML model is loaded correctly
2. Check if new threat patterns need to be added
3. Review noise rules for overly aggressive patterns

### Performance Issues

#### "High latency (P99 > 100ms)"

1. Check batch size - may need to reduce
2. Check memory usage - may need more resources
3. Check if ML model is too complex
4. Verify Kafka consumer is not backpressured

#### "Out of memory errors"

1. Increase pod memory limits
2. Reduce batch size
3. Check for memory leaks in custom rules

### Connectivity Issues

#### "QRadar connection failures"

1. Verify network connectivity:
   ```bash
   kubectl exec -it deploy/ai-log-filter -- curl -v https://qradar:443/api/health
   ```
2. Check QRadar token validity
3. Verify SSL certificate

#### "Kafka connection failures"

1. Check Kafka cluster health
2. Verify bootstrap servers in config
3. Check network policies

---

## Maintenance Procedures

### Model Update Procedure

1. **Prepare new model:**

   ```bash
   # Train and evaluate
   python scripts/train.py --config configs/model_config.yaml
   python scripts/evaluate.py --model models/new_version --test-data data/test.csv
   ```

2. **Validate performance:**
   - Critical recall > 99.5%
   - False negative rate < 0.5%
   - Latency P99 < 100ms

3. **Deploy to staging:**

   ```bash
   kubectl apply -f deploy/kubernetes/staging/
   ```

4. **Run shadow mode validation (24-72 hours)**

5. **Deploy to production:**

   ```bash
   kubectl set image deployment/ai-log-filter ai-filter=ai-log-filter:v1.1.0
   ```

6. **Monitor for 1 hour, then proceed or rollback**

### Rule Update Procedure

1. **Edit rules.yaml**
2. **Validate syntax:**
   ```bash
   python -c "import yaml; yaml.safe_load(open('configs/rules.yaml'))"
   ```
3. **Test rules:**
   ```bash
   python scripts/test_rules.py --rules configs/rules.yaml --samples data/test_samples.json
   ```
4. **Deploy:**
   ```bash
   kubectl rollout restart deployment/ai-log-filter
   ```

---

## Rollback Procedures

### Immediate Rollback (Model Issue)

```bash
# Rollback to previous deployment
kubectl rollout undo deployment/ai-log-filter

# Verify rollback
kubectl rollout status deployment/ai-log-filter
```

### Rollback to Specific Version

```bash
# List revision history
kubectl rollout history deployment/ai-log-filter

# Rollback to specific revision
kubectl rollout undo deployment/ai-log-filter --to-revision=3
```

### Emergency Bypass Mode

If AI filter is causing issues and cannot be fixed quickly:

1. **Activate bypass mode (all logs to QRadar):**

   ```bash
   kubectl set env deployment/ai-log-filter BYPASS_MODE=true
   ```

2. **This will:**
   - Forward all logs directly to QRadar
   - Continue archiving to cold storage
   - Log all bypass decisions for audit

3. **Deactivate bypass mode:**
   ```bash
   kubectl set env deployment/ai-log-filter BYPASS_MODE-
   ```

---

## Contact Information

| Role               | Contact                   | Escalation Time |
| ------------------ | ------------------------- | --------------- |
| On-Call Engineer   | PagerDuty                 | 5 min           |
| Security Team Lead | security-lead@company.com | 15 min          |
| Platform Team      | platform@company.com      | 30 min          |
| Vendor Support     | IBM QRadar Support        | 1 hour          |

---

_Document Version: 1.0_  
_Last Updated: January 2026_  
_Owner: Security Operations_
