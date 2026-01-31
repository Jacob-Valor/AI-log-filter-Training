# ONNX Quick Start Guide

[Back to docs index](../README.md) • [Performance index](README.md)

## ⚡ 3-Step Migration

### Step 1: Install (30 seconds)
```bash
# Recommended (uses `uv.lock`)
uv sync --extra dev --extra onnx --extra onnxruntime

# Or pip (installs project extras)
# Note: onnxruntime wheels may lag newest Python versions.
pip install ".[onnx,onnxruntime]"
```

### Step 2: Convert (1 minute)
```bash
python scripts/convert_models_to_onnx.py \
    --input models/v3 \
    --output models/v3/onnx \
    --benchmark
```

### Step 3: Use (change 3 lines)
```python
# OLD
from src.models.anomaly_detector import AnomalyDetector
detector = AnomalyDetector(config)

# NEW
from src.models.onnx_runtime import ONNXAnomalyDetector
detector = ONNXAnomalyDetector({
    "model_path": "models/v3/onnx/anomaly_detector.onnx",
    "scaler_path": "models/v3/onnx/scaler.joblib",
})
```

## 📊 Results You Can Expect

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| **Inference** | 0.82 ms | 0.10 ms | **8x faster** |
| **Model Size** | 1.43 MB | 0.31 MB | **78% smaller** |
| **Load Time** | 47 ms | 5 ms | **10x faster** |
| **Memory** | 15 MB | 6 MB | **60% less** |
| **Throughput** | 121K EPS | 1.02M EPS | **8x higher** |

## 🤔 When to Use ONNX

### ✅ DO use ONNX if:
- Processing > 10,000 EPS
- Need lower latency
- Want smaller containers
- Deploying to edge/IoT

### ❌ DON'T use ONNX if:
- Current performance is sufficient
- Want simpler debugging
- Avoiding new dependencies

## 🔄 Rollback

Still have joblib models? Just use them:
```python
from src.models.anomaly_detector import AnomalyDetector  # Still works!
```

## 📚 Full Documentation

See [ONNX_MIGRATION_GUIDE.md](ONNX_MIGRATION_GUIDE.md) for complete details.
