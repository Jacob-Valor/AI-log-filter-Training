# Cost Tracking - Quick Start Guide

## 1. Quick Demo (5 Minutes)

```bash
# Run the cost report generator
python scripts/cost_report.py --format terminal --qradar-eps 15000

# Generate a markdown report
python scripts/cost_report.py --format markdown --output reports/cost_report.md

# Generate a JSON report
python scripts/cost_report.py --format json --output reports/cost_report.json
```

## 2. Integration (10 Minutes)

### Step 1: Add to Main Application

Edit `src/main.py`:

```python
from src.monitoring.cost_tracker import init_cost_tracker, get_cost_tracker

# Initialize cost tracker with your QRadar EPS capacity
cost_tracker = init_cost_tracker(current_qradar_eps=15000)

# In your processing loop, record EPS data
def process_logs(logs):
    eps_before = len(logs) / processing_time
    eps_after = len(filtered_logs) / processing_time
    reduction_ratio = (eps_before - eps_after) / eps_before

    # Record to cost tracker
    cost_tracker.record_eps_data(eps_before, eps_after, reduction_ratio)
```

### Step 2: Import Grafana Dashboard

1. Open Grafana: http://localhost:3000
2. Go to **Dashboards** → **Import**
3. Upload: `configs/grafana/dashboards/cost_dashboard.json`
4. Select Prometheus data source
5. Click **Import**

### Step 3: Verify Metrics

```bash
# Check that cost metrics are being exported
curl http://localhost:9091/metrics | grep ai_filter_cost

# You should see:
# ai_filter_cost_savings_hourly_usd
# ai_filter_cost_savings_daily_usd
# ai_filter_cost_savings_monthly_usd
# ai_filter_cost_savings_annual_usd
# ai_filter_roi_days_to_break_even
# ai_filter_roi_percentage
# ... and more
```

## 3. Customization (5 Minutes)

### Adjust QRadar Pricing

Edit `src/monitoring/cost_tracker.py`:

```python
QRADAR_PRICING_TIERS = {
    "basic": {
        "max_eps": 5_000,
        "annual_cost": 150_000,  # ← YOUR PRICE
        "description": "Basic SIEM license"
    },
    "standard": {
        "max_eps": 15_000,
        "annual_cost": 450_000,  # ← YOUR PRICE
        "description": "Standard SIEM license"
    },
    # ... more tiers
}
```

### Adjust Infrastructure Costs

Edit `src/monitoring/cost_tracker.py`:

```python
INFRASTRUCTURE_COSTS = {
    "kafka_cluster": {
        "annual_cost": 12_000,  # ← YOUR COST
        "description": "Kafka cluster hosting"
    },
    "compute": {
        "annual_cost": 24_000,  # ← YOUR COST
        "description": "AI filter compute instances"
    },
    # ... more components
}
```

## 4. Setup Automated Reports (5 Minutes)

### Daily Cost Report (Cron)

```bash
# Edit crontab
crontab -e

# Add daily report at 8 AM
0 8 * * * cd /home/jacob/Projects/tester && \
  python scripts/cost_report.py \
    --format markdown \
    --output reports/daily/$(date +\%Y-\%m-\%d).md
```

### Weekly Email Report

```bash
#!/bin/bash
# scripts/weekly_cost_report.sh

DATE=$(date +%Y-%m-%d)
REPORT_FILE="reports/weekly/weekly_${DATE}.md"

mkdir -p reports/weekly
python scripts/cost_report.py \
  --format markdown \
  --output "$REPORT_FILE"

# Email the report (requires mail command)
mail -s "AI Filter Weekly Cost Report" finance@company.com < "$REPORT_FILE"
```

Add to crontab:

```bash
# Weekly report every Monday at 9 AM
0 9 * * 1 /home/jacob/Projects/tester/scripts/weekly_cost_report.sh
```

## 5. Cost Alerts (5 Minutes)

Add to `configs/prometheus-alerts.yaml`:

```yaml
groups:
  - name: cost_alerts
    interval: 1m
    rules:
      # Alert if savings drop below $15K/month
      - alert: CostSavingsBelowTarget
        expr: ai_filter_cost_savings_monthly_usd < 15000
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: "Cost savings below $15K/month target"
          description: "Current monthly savings: ${{ $value }}"

      # Alert if ROI is negative after 6 months
      - alert: NegativeROI
        expr: ai_filter_roi_percentage < 0
        for: 180d
        labels:
          severity: critical
        annotations:
          summary: "Negative ROI after 6 months"
          description: "ROI is {{ $value }}%"

      # Alert if break-even exceeds 6 months
      - alert: BreakEvenTooLong
        expr: ai_filter_roi_days_to_break_even > 180
        annotations:
          summary: "Break-even period exceeds 6 months"
          description: "Days to break-even: {{ $value }}"
```

Reload Prometheus:

```bash
# Reload Prometheus configuration
curl -X POST http://localhost:9091/-/reload
```

## 6. Common Use Cases

### Use Case 1: Prove ROI to Stakeholders

```bash
# Generate executive summary report
python scripts/cost_report.py \
  --format markdown \
  --output reports/executive/roi_summary.md

# Include in:
# - Quarterly business reviews
# - Budget proposals
# - ROI presentations
```

### Use Case 2: Track Financial Impact

```bash
# Generate daily report for tracking
python scripts/cost_report.py \
  --format json \
  --output reports/daily/$(date +%Y-%m-%d).json

# Archive for:
# - Historical trend analysis
# - Budget reconciliation
# - Performance reviews
```

### Use Case 3: Monitor Cost Efficiency

```bash
# Check cost metrics in real-time
curl http://localhost:9091/metrics | grep ai_filter_cost

# Look at Grafana dashboard:
# → http://localhost:3000
# → "AI Log Filter - Cost & Savings Dashboard"
```

### Use Case 4: Optimization Analysis

```bash
# Generate report before optimization
python scripts/cost_report.py --output before.md

# [Make optimization]

# Generate report after optimization
python scripts/cost_report.py --output after.md

# Compare savings increase
```

## 7. Troubleshooting

### Problem: Cost savings showing as $0

**Solution:**

```bash
# Verify EPS data is being recorded
curl http://localhost:9091/metrics | grep ai_filter_eps

# Should see:
# ai_filter_eps_ingested
# ai_filter_eps_to_qradar
# ai_filter_eps_filtered
# ai_filter_eps_reduction_ratio
```

### Problem: ROI showing negative (after months)

**Solution:**

```bash
# Check infrastructure costs are correct
grep -A 20 "INFRASTRUCTURE_COSTS" src/monitoring/cost_tracker.py

# Verify QRadar pricing is correct
grep -A 20 "QRADAR_PRICING_TIERS" src/monitoring/cost_tracker.py
```

### Problem: Grafana dashboard not showing data

**Solution:**

```bash
# Check Prometheus is scraping metrics
curl http://localhost:9091/metrics | grep ai_filter_cost

# Check Grafana data source
# → Grafana → Configuration → Data Sources → Prometheus → Test

# Check query syntax in Grafana panel
# → Grafana → Dashboard → Panel → Edit → Query
```

## 8. Quick Reference

### Command Line Options

```bash
# Terminal output (colorized, best for demos)
--format terminal

# Markdown output (best for documentation)
--format markdown

# JSON output (best for API integration)
--format json

# Text output (best for email)
--format text

# Set QRadar EPS capacity
--qradar-eps 15000

# Save to file
--output reports/cost_report.md
```

### Key Metrics to Monitor

| Metric             | Target               | Alert If             |
| ------------------ | -------------------- | -------------------- |
| Monthly Savings    | >$15K                | <$15K                |
| ROI Percentage     | >100% (after 1 year) | <0% (after 6 months) |
| Days to Break Even | <90 days             | >180 days            |
| Cost Reduction     | >40%                 | <30%                 |

### Dashboard Panels

1. **Annual Cost Savings** - Main KPI
2. **Daily Cost Savings** - Daily tracking
3. **Days to Break Even** - ROI timeline
4. **ROI Percentage** - Return metric
5. **Cost Savings Trend** - 30-day history
6. **ROI Trend** - ROI over time
7. **Cost Savings by Category** - Pie breakdown
8. **Cost Reduction %** - Efficiency gauge
9. **Infrastructure vs QRadar** - Cost comparison

## 9. Next Steps

1. ✅ **Run demo report** (5 min)
2. ✅ **Integrate into app** (10 min)
3. ✅ **Import Grafana dashboard** (5 min)
4. ✅ **Customize pricing** (5 min)
5. ✅ **Setup automated reports** (5 min)
6. ✅ **Configure alerts** (5 min)
7. ✅ **Generate first executive report** (2 min)

**Total Time:** ~37 minutes

---

**Documentation:** See `docs/cost_tracking.md` for detailed documentation
**Support:** Check Grafana dashboard for real-time metrics
**Examples:** See `reports/cost_report.md` for sample output
