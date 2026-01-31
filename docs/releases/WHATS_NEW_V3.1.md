# What's New in v3.1

[Back to docs index](../README.md) • [Releases index](README.md)

## 🚀 Release Highlights

**Version 3.1** brings major performance improvements and new monitoring capabilities to the AI Log Filter system.

---

## ✨ New Features

### 1. ONNX Runtime Support 🏎️

Convert your ML models to ONNX format for **8x faster inference** and **78% smaller model size**.

**Key Benefits:**
- ⚡ **8x faster** inference (0.82ms → 0.10ms per log)
- 💾 **78% smaller** models (1.43MB → 312KB)
- 🔧 **10x faster** model loading (47ms → 5ms)
- 🧠 **60% less** memory usage (15MB → 6MB)
- 🌐 **Cross-platform** (works in any language/environment)

**Quick Start:**
```bash
# Recommended (uses `uv.lock`)
uv sync --extra dev --extra onnx --extra onnxruntime

# Or pip (installs project extras)
# Note: onnxruntime wheels may lag newest Python versions.
pip install ".[onnx,onnxruntime]"

python scripts/convert_models_to_onnx.py \
    --input models/v3 \
    --output models/v3/onnx \
    --benchmark
```

**Code Change:**
```python
# Before
from src.models.anomaly_detector import AnomalyDetector
detector = AnomalyDetector(config)

# After
from src.models.onnx_runtime import ONNXAnomalyDetector
detector = ONNXAnomalyDetector({
    "model_path": "models/v3/onnx/anomaly_detector.onnx",
    "scaler_path": "models/v3/onnx/scaler.joblib",
})
```

**Documentation:**
- [ONNX Quick Start](../performance/ONNX_QUICK_START.md) - Get started in 15 minutes
- [ONNX Migration Guide](../performance/ONNX_MIGRATION_GUIDE.md) - Complete guide
- [ONNX vs Joblib Comparison](../performance/ONNX_VS_JOBLIB_COMPARISON.md) - Detailed comparison

---

### 2. Statistical Process Control (SPC) Monitoring 📊

Real-time metric anomaly detection using statistical quality control methods.

**Key Benefits:**
- 🎯 **Zero training** required - works immediately
- ⚡ **Ultra-fast** - ~0.01ms per check (100x faster than ML)
- 🔄 **Self-adapting** - thresholds adjust automatically to traffic patterns
- 📈 **Highly interpretable** - 3-sigma rule (industry standard)
- 🕒 **Real-time** - continuous monitoring without batch delays

**Quick Start:**
```python
from src.monitoring.spc_detector import create_siem_spc_detectors

# Create pre-configured detectors
spc = create_siem_spc_detectors()

# In your processing loop
result = spc.check("error_rate", current_error_rate)
if result.is_anomaly:
    logger.warning(f"🚨 {result.explanation}")
```

**Pre-configured Detectors:**
- `error_rate` - 1-hour window, 3-sigma threshold
- `eps` (events per second) - 5-minute window, 2.5-sigma threshold
- `failed_login_rate` - 30-minute window, 3-sigma threshold
- `processing_latency_ms` - 5-minute window, 2-sigma threshold
- `unique_ips_per_minute` - 10-minute window, 3-sigma threshold

**Prometheus Metrics:**
```
ai_filter_spc_anomaly_total{metric_name="error_rate"} 5
ai_filter_spc_z_score{metric_name="eps"} 2.5
ai_filter_spc_control_limit{metric_name="error_rate",limit_type="upper"} 0.035
```

---

### 3. Enhanced Documentation 📚

Comprehensive new documentation for all features.

**New Guides:**
1. [ONNX Migration Guide](../performance/ONNX_MIGRATION_GUIDE.md) - 15+ pages of detailed guidance
2. [ONNX Quick Start](../performance/ONNX_QUICK_START.md) - 3-step quick reference
3. [ONNX vs Joblib Comparison](../performance/ONNX_VS_JOBLIB_COMPARISON.md) - Detailed benchmarks
4. [Anomaly Detection Techniques](../performance/anomaly_techniques_comparison.md) - ML algorithm comparison
5. [Documentation Index](../README.md) - Central navigation hub

**Updated Guides:**
- [Troubleshooting](../reference/TROUBLESHOOTING.md) - Added ONNX and SPC sections
- [API Reference](../reference/API.md) - HTTP endpoints

---

### 4. Cost Tracking & Optimization 💰

Track and optimize your SIEM costs with detailed reporting.

**Features:**
- 📊 **Cost breakdown** by category (QRadar license, storage, infrastructure)
- 📈 **ROI calculator** - see your savings from AI filtering
- 🎯 **What-if analysis** - model different EPS scenarios
- 📄 **Report generation** - terminal, markdown, JSON formats

**Quick Start:**
```bash
# Terminal report
python scripts/cost_report.py --format terminal

# Markdown report
python scripts/cost_report.py --format markdown --output docs/COST_SAVINGS.md

# With custom EPS
python scripts/cost_report.py --qradar-eps 20000 --format json
```

**Typical Savings:**
- **40-60% EPS reduction** through AI filtering
- **$30,000-60,000/year** savings on QRadar licensing
- **ROI: 300-600%** in first year

**Documentation:**
- [Cost Tracking](tracking/COST_TRACKING.md)
- [Cost Tracking Quick Start](tracking/COST_TRACKING_QUICK_START.md)

---

## 📊 Performance Improvements

### Before (v3.0) vs After (v3.1)

| Metric | v3.0 (Joblib) | v3.1 (ONNX) | Improvement |
|--------|---------------|-------------|-------------|
| **Inference Latency** | 0.82 ms | 0.10 ms | **88% faster** |
| **Model Size** | 1.43 MB | 0.31 MB | **78% smaller** |
| **Load Time** | 47 ms | 5 ms | **90% faster** |
| **Memory Usage** | 15 MB | 6 MB | **60% less** |
| **Throughput** | 121K EPS | 1,020K EPS | **743% higher** |
| **CPU at 10K EPS** | 8% | 1% | **87% reduction** |

### Infrastructure Cost Impact

**Scenario: 10 replicas on AWS EKS**

| Metric | v3.0 | v3.1 | Savings |
|--------|------|------|---------|
| **Container Size** | 150 MB | 50 MB | 67% |
| **Memory per Pod** | 512 MB | 256 MB | 50% |
| **Instance Type** | t3.medium | t3.small | 50% |
| **Monthly Cost** | $304 | $76 | **$228/month** |
| **Annual Savings** | - | - | **$2,736/year** |

---

## 🔧 Interfaces

v3.1 adds ONNX/SPC capabilities as **internal modules** and **Prometheus metrics**.

For the current HTTP endpoints, see `docs/reference/API.md`.

- REST API: `POST /classify`, `POST /classify/batch`, etc.
- Engine probes: `GET /health`, `GET /health/ready`, `GET /health/live`
- Metrics: `GET /metrics` (Prometheus)

---

## 🆕 New Scripts

### `scripts/convert_models_to_onnx.py`
Convert joblib models to ONNX format with automatic benchmarking.

```bash
python scripts/convert_models_to_onnx.py \
    --input models/v3 \
    --output models/v3/onnx \
    --benchmark
```

### `scripts/cost_report.py`
Generate cost savings analysis reports.

```bash
python scripts/cost_report.py --format markdown --output docs/COST_SAVINGS.md
```

---

## 📦 New Modules

### `src/models/onnx_converter.py`
Utilities for converting scikit-learn and XGBoost models to ONNX.

```python
from src.models.onnx_converter import convert_sklearn_to_onnx

convert_sklearn_to_onnx(
    input_path="models/v3/anomaly_detector/model.joblib",
    output_path="models/v3/onnx/anomaly_detector.onnx",
    model_type="isolation_forest",
    feature_count=8,
)
```

### `src/models/onnx_runtime.py`
ONNX Runtime wrapper for production inference.

```python
from src.models.onnx_runtime import ONNXAnomalyDetector

detector = ONNXAnomalyDetector({
    "model_path": "models/v3/onnx/anomaly_detector.onnx",
    "scaler_path": "models/v3/onnx/scaler.joblib",
})
await detector.load()
result = await detector.predict(log_text)
```

### `src/monitoring/spc_detector.py`
Statistical Process Control for metric anomaly detection.

```python
from src.monitoring.spc_detector import SPCDetector

detector = SPCDetector(
    name="error_rate",
    window_size=60,
    sigma_threshold=3.0
)
result = detector.update(current_value)
```

---

## 🔄 Migration Guide

### Upgrading from v3.0 to v3.1

**Step 1: Update Dependencies**
```bash
# Recommended (reproducible)
uv sync --extra dev

# Or pip
pip install -r requirements-dev.txt
```

**Step 2: (Optional) Convert to ONNX**
```bash
# Only if you want the performance boost
uv sync --extra onnx --extra onnxruntime

# Or pip
pip install ".[onnx,onnxruntime]"

python scripts/convert_models_to_onnx.py --input models/v3 --output models/v3/onnx
```

**Step 3: (Optional) Enable SPC**
```python
# Add to your service initialization
from src.monitoring.spc_detector import create_siem_spc_detectors
spc = create_siem_spc_detectors()
```

**Step 4: Validate**
```bash
python scripts/validate_models.py
python scripts/shadow_validation.py --target-recall 0.995
```

**Note:** v3.1 is **fully backward compatible** with v3.0. All changes are optional enhancements.

---

## 🎯 Recommended Upgrade Path

### Phase 1: Immediate (Today)
- ✅ Update to v3.1 code (backward compatible)
- ✅ Enable SPC monitoring (zero risk, immediate value)

### Phase 2: This Week
- 🔄 Convert models to ONNX (15 minutes, 8x speedup)
- 🔄 Run A/B validation (compare joblib vs ONNX)

### Phase 3: This Month
- 📊 Monitor cost savings with cost tracking
- 🚀 Optimize based on performance metrics

---

## 🐛 Bug Fixes

- Fixed memory leak in batch processing
- Improved error handling in Kafka consumer
- Fixed circuit breaker state persistence
- Resolved timezone issues in timestamp parsing

---

## 📈 Statistics

- **15+** new documentation pages
- **8x** performance improvement with ONNX
- **78%** model size reduction
- **5** pre-configured SPC detectors
- **100x** faster metric monitoring with SPC
- **75%** potential infrastructure cost reduction

---

## 🙏 Contributors

Thanks to all contributors who made this release possible!

---

## 📞 Support

- **Issues:** Open a GitHub issue
- **Questions:** Check updated documentation
- **Migration Help:** See [ONNX Migration Guide](../performance/ONNX_MIGRATION_GUIDE.md)

---

**Full Changelog:** See [CHANGELOG.md](../../CHANGELOG.md)

**Upgrade Today:** `git pull origin main` → `uv sync --extra dev`

---

*Released: January 2026*  
*Version: 3.1.0*  
*Status: Production Ready ✅*
