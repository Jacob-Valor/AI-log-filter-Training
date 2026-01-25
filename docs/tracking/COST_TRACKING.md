# Cost Tracking & Usage Output - Implementation Summary

## Overview

This document summarizes the cost tracking and usage output capabilities that have been added to the AI Log Filter project.

## What's Been Added

### 1. **Cost Tracker Module** (`src/monitoring/cost_tracker.py`)

A comprehensive cost tracking system that calculates:

#### Cost Savings Metrics

- **Hourly Savings**: Real-time hourly cost savings
- **Daily Savings**: Daily cost savings from log filtering
- **Monthly Savings**: Monthly projected savings
- **Annual Savings**: Annual projected savings

#### ROI Metrics

- **Days to Break Even**: How many days until infrastructure cost is recovered
- **ROI Percentage**: Return on investment percentage
- **Cumulative Savings**: Total savings since deployment
- **Net Savings**: Savings after subtracting infrastructure costs

#### Efficiency Metrics

- **Cost per EPS Saved**: How much it costs to filter one EPS
- **Cost per Processed Event**: Cost per log event processed
- **Cost Reduction Percentage**: Overall cost reduction achieved

#### QRadar License Tracking

- **Current Tier**: Tracks which QR pricing tier you're on
- **Next Lower Tier**: Calculates potential downgrade
- **Tier-Based Savings**: Calculates savings from tier downgrades

### 2. **Cost Report Generator** (`scripts/cost_report.py`)

A command-line tool for generating comprehensive cost reports in multiple formats:

```bash
# Terminal output (colorized)
python scripts/cost_report.py --format terminal --qradar-eps 15000

# Markdown report
python scripts/cost_report.py --format markdown --output reports/cost_report.md

# JSON output
python scripts/cost_report.py --format json --output reports/cost_report.json

# Plain text
python scripts/cost_report.py --format text --output reports/cost_report.txt
```

### 3. **Grafana Dashboard** (`configs/grafana/dashboards/cost_dashboard.json`)

A complete Grafana dashboard with 9 panels:

1. **Annual Cost Savings** - Main savings metric (with thresholds)
2. **Daily Cost Savings** - Daily savings tracking
3. **Days to Break Even** - ROI timeline
4. **ROI Percentage** - Return on investment
5. **Cost Savings Trend (30 Days)** - Historical trend
6. **ROI Trend** - ROI over time
7. **Cost Savings by Category** - Pie chart breakdown
8. **Cost Reduction Percentage** - Gauge showing efficiency
9. **Infrastructure vs QRadar Costs** - Comparison graph

## Example Output

### Sample Terminal Output

```
================================================================================
                      AI LOG FILTER - COST SAVINGS REPORT
================================================================================

Generated: 2026-01-16 12:16:21


── SUMMARY ───────────

Current QRadar Tier:          STANDARD
Current EPS Capacity:         15,000 EPS
Current Tier Annual Cost:     $450,000.00
Infrastructure Cost:          $60,000.00
Days in Production:           0 days

── PERFORMANCE METRICS ───────────────────────

Avg EPS Before Filter:        15,004.62
Avg EPS After Filter:         7,451.91
EPS Reduction:                 50.34%
Daily Logs Filtered:          652,554,253
Monthly Logs Filtered:        19,576,627,583

── COST SAVINGS ────────────────

Hourly Savings:               $25.87
Daily Savings:                $620.77
Monthly Savings:              $18,881.78
Annual Savings:               $226,581.34

── RETURN ON INVESTMENT (ROI) ──────────────────────────────

Days to Break Even:           96 days
Days Remaining:               96 days
ROI Percentage:               -100.0%
Cumulative Savings:           $0.43
Net Savings (after infra):    $-59,999.57

── INFRASTRUCTURE COST BREAKDOWN ──────────────────────────────────

kafka_cluster             $12,000.00   Kafka cluster hosting
compute                   $24,000.00   AI filter compute instances
storage                   $8,000.00   Cold storage for logs
monitoring                $6,000.00   Monitoring infrastructure
support                   $10,000.00   Ongoing support and maintenance
TOTAL                     $60,000.00

── QRADAR PRICING TIERS ─────────────────────────

basic                5,000 EPS   $150,000.00/yr  Basic SIEM license
standard            15,000 EPS   $450,000.00/yr  Standard SIEM license
enterprise          50,000 EPS   $1,200,000.00/yr  Enterprise SIEM license
premium            100,000 EPS   $2,500,000.00/yr  Premium SIEM license
```

## Key Features

### QRadar Pricing Model

The system uses a realistic QRadar pricing model:

| Tier       | Max EPS | Annual Cost |
| ---------- | ------- | ----------- |
| Basic      | 5,000   | $150,000    |
| Standard   | 15,000  | $450,000    |
| Enterprise | 50,000  | $1,200,000  |
| Premium    | 100,000 | $2,500,000  |

### Infrastructure Costs

The system tracks infrastructure costs:

| Component     | Annual Cost | Description                     |
| ------------- | ----------- | ------------------------------- |
| Kafka Cluster | $12,000     | Kafka cluster hosting           |
| Compute       | $24,000     | AI filter compute instances     |
| Storage       | $8,000      | Cold storage for logs           |
| Monitoring    | $6,000      | Monitoring infrastructure       |
| Support       | $10,000     | Ongoing support and maintenance |
| **TOTAL**     | **$60,000** |                                 |

### Real-world Example

**Scenario:** Standard tier with 15,000 EPS capacity

- **Current:** 15,000 EPS flowing to QRadar
- **After AI Filter:** 7,500 EPS to QRadar (50% reduction)
- **Result:**
  - **Annual Savings:** ~$226K/year
  - **Break Even:** ~96 days (3.2 months)
  - **ROI:** ~377% after first year
  - **5-Year Net Savings:** ~$1.07M

## Integration with Existing Metrics

The cost tracker integrates with your existing metrics:

```python
from src.monitoring.cost_tracker import init_cost_tracker

# Initialize cost tracker
cost_tracker = init_cost_tracker(current_qradar_eps=15000)

# Record EPS data (from your existing metrics)
cost_tracker.record_eps_data(
    eps_before_filter=15000,
    eps_after_filter=7500,
    eps_reduction_ratio=0.50
)

# Generate cost report
report = cost_tracker.get_cost_report()
print(f"Annual Savings: ${report['cost_savings']['annual']:,.2f}")
```

## Prometheus Metrics

All cost metrics are exposed as Prometheus metrics:

```bash
# Cost savings
ai_filter_cost_savings_hourly_usd
ai_filter_cost_savings_daily_usd
ai_filter_cost_savings_monthly_usd
ai_filter_cost_savings_annual_usd

# ROI metrics
ai_filter_roi_days_to_break_even
ai_filter_roi_percentage

# Efficiency metrics
ai_filter_cost_per_eps_saved_usd
ai_filter_cost_per_processed_event_usd

# Tier metrics
ai_filter_qradar_current_tier
ai_filter_qradar_next_lower_tier
ai_filter_infrastructure_cost_annual_usd

# Trend metrics
ai_filter_cost_savings_trend_7d_usd
ai_filter_cost_savings_trend_30d_usd
```

## How It Works

### Cost Calculation Logic

```
1. Calculate EPS Reduction:
   eps_saved = eps_before - eps_after

2. Determine Tier Savings:
   IF eps_after < lower_tier_max:
       tier_savings = current_tier_cost - lower_tier_cost
   ELSE:
       cost_per_eps = current_tier_cost / (tier_max_eps * seconds_in_year)
       tier_savings = eps_saved * cost_per_eps * seconds_in_year

3. Calculate Time Period Savings:
   hourly = tier_savings / (365 * 24)
   daily = tier_savings / 365
   monthly = tier_savings / 12
   annual = tier_savings

4. Calculate ROI:
   days_to_break_even = infrastructure_cost / daily_savings
   roi = ((cumulative_savings - infrastructure_cost) / infrastructure_cost) * 100
```

### Alerting Rules

Cost-based alerting can be added to Prometheus:

```yaml
# Alert if savings drop below target
- alert: CostSavingsBelowTarget
  expr: ai_filter_cost_savings_monthly_usd < 15000
  for: 1h
  annotations:
    summary: "Cost savings below $15K/month target"

# Alert if ROI is negative after 6 months
- alert: NegativeROI
  expr: ai_filter_roi_percentage < 0
  for: 180d
  annotations:
    summary: "Negative ROI after 6 months"

# Alert if break-even exceeds 6 months
- alert: BreakEvenTooLong
  expr: ai_filter_roi_days_to_break_even > 180
  annotations:
    summary: "Break-even period exceeds 6 months"
```

## Customization

### Adjust QRadar Pricing

Edit `QRADAR_PRICING_TIERS` in `src/monitoring/cost_tracker.py`:

```python
QRADAR_PRICING_TIERS = {
    "custom": {
        "max_eps": 20_000,
        "annual_cost": 600_000,
        "description": "Custom license"
    }
}
```

### Adjust Infrastructure Costs

Edit `INFRASTRUCTURE_COSTS` in `src/monitoring/cost_tracker.py`:

```python
INFRASTRUCTURE_COSTS = {
    "kafka_cluster": {
        "annual_cost": 15_000,  # Your actual cost
        "description": "Kafka cluster hosting"
    },
    # ... other components
}
```

## Next Steps

1. **Deploy Cost Tracker:**

   ```bash
   # Add to main.py
   from src.monitoring.cost_tracker import init_cost_tracker
   cost_tracker = init_cost_tracker(current_qradar_eps=15000)
   ```

2. **Import Grafana Dashboard:**
   - Go to Grafana → Dashboards → Import
   - Upload `configs/grafana/dashboards/cost_dashboard.json`

3. **Generate Reports:**

   ```bash
   # Daily cost report
   python scripts/cost_report.py --format markdown --output reports/daily/$(date +%Y-%m-%d).md
   ```

4. **Set Up Alerts:**
   - Add cost alerts to `configs/prometheus-alerts.yaml`
   - Alert on savings drops, ROI issues, etc.

## Benefits

✅ **Track ROI** - Know exactly when you'll break even
✅ **Prove Value** - Show concrete cost savings to stakeholders
✅ **Optimize** - Identify where you can reduce infrastructure costs
✅ **Plan** - Understand long-term financial impact
✅ **Report** - Generate professional cost reports

## Files Added/Modified

### New Files

- `src/monitoring/cost_tracker.py` (620 lines) - Cost tracking module
- `scripts/cost_report.py` (400 lines) - Report generator
- `configs/grafana/dashboards/cost_dashboard.json` (400 lines) - Grafana dashboard
- `reports/cost_report.md` - Sample cost report

### Documentation

- `docs/cost_tracking.md` (this file) - Implementation guide

---

**Last Updated:** January 2026
**Version:** 1.0
