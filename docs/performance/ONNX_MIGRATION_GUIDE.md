# ONNX Migration Guide

[Back to docs index](../README.md) • [Performance index](README.md)

## Overview

This guide explains how to migrate from joblib-based models to **ONNX (Open Neural Network Exchange)** format for significantly faster inference and smaller model sizes.

## Quick Summary

| Metric | Joblib | ONNX | Improvement |
|--------|--------|------|-------------|
| **Inference Speed** | ~0.8ms/log | ~0.1ms/log | **8x faster** |
| **Model Size** | ~1.4 MB | ~300 KB | **78% smaller** |
| **Memory Usage** | Higher | Lower | **~60% reduction** |
| **Load Time** | ~50ms | ~5ms | **10x faster** |
| **Cross-Platform** | Python only | Any language | **Universal** |

## Should You Migrate?

### ✅ **YES, if:**
- You need to process more than 10,000 EPS (Events Per Second)
- You're running on resource-constrained environments (edge, IoT)
- You want faster model loading times
- You plan to deploy to non-Python environments (C++, C#, Java)
- You're using Kubernetes and want smaller container images
- You need lower latency for real-time processing

### ⚠️ **MAYBE NOT, if:**
- Your current 10K EPS target is sufficient
- You don't want to add new dependencies
- You prefer simpler debugging (joblib is easier to inspect)
- You're in maintenance mode and don't need optimization

## Installation

### Step 1: Install ONNX Dependencies

```bash
# Recommended (uses `uv.lock`)
uv sync --extra dev --extra onnx --extra onnxruntime

# Or pip (installs project extras)
# Note: onnxruntime wheels may lag newest Python versions.
pip install ".[onnx,onnxruntime]"
```

### Step 2: Verify Installation

```bash
python -c "import onnxruntime; print('ONNX Runtime:', onnxruntime.__version__)"
python -c "import skl2onnx; print('skl2onnx:', skl2onnx.__version__)"
```

## Converting Your Models

### Option A: Automatic Conversion Script

```bash
# Convert all models with benchmarking
python scripts/convert_models_to_onnx.py \
    --input models/v3 \
    --output models/v3/onnx \
    --benchmark

# Convert only anomaly detector
python scripts/convert_models_to_onnx.py \
    --input models/v3 \
    --output models/v3/onnx \
    --model anomaly

# Convert only XGBoost
python scripts/convert_models_to_onnx.py \
    --input models/v3 \
    --output models/v3/onnx \
    --model xgboost
```

**Expected Output:**
```
============================================================
CONVERTING ANOMALY DETECTOR
============================================================
Input:  models/v3/anomaly_detector/model.joblib
Output: models/v3/onnx/anomaly_detector.onnx
Loading joblib model...
✓ Scaler saved to models/v3/onnx/scaler.joblib
Converting to ONNX format...
✓ ONNX model saved

Size Comparison:
  Original:  1433.6 KB
  ONNX:      312.4 KB
  Reduction: 78.2% smaller

------------------------------------------------------------
BENCHMARKING
------------------------------------------------------------
Results (1000 iterations, 100 samples each):
  Joblib:  0.823 ms/inference
  ONNX:    0.098 ms/inference
  Speedup: 8.40x faster
  Improvement: 740.0%

Throughput (100-sample batches):
  Joblib:  121,507 EPS
  ONNX:    1,020,408 EPS
```

### Option B: Manual Conversion

```python
from src.models.onnx_converter import convert_sklearn_to_onnx

# Convert anomaly detector
convert_sklearn_to_onnx(
    input_path="models/v3/anomaly_detector/model.joblib",
    output_path="models/v3/onnx/anomaly_detector.onnx",
    model_type="isolation_forest",
    feature_count=8,
)

# Convert XGBoost model
from src.models.onnx_converter import convert_xgboost_to_onnx

convert_xgboost_to_onnx(
    input_path="models/v3/tfidf_xgboost/model.joblib",
    output_path="models/v3/onnx/xgboost.onnx",
    feature_count=10000,
)
```

## Using ONNX Models in Production

### Option A: Drop-in Replacement (Recommended)

Replace your existing detector with the ONNX version:

```python
# OLD: Joblib-based
from src.models.anomaly_detector import AnomalyDetector

detector = AnomalyDetector({
    "contamination": 0.1,
    "n_estimators": 200,
})
await detector.load()  # Loads from models/v3/anomaly_detector/model.joblib

# NEW: ONNX-based (drop-in replacement)
from src.models.onnx_runtime import ONNXAnomalyDetector

detector = ONNXAnomalyDetector({
    "model_path": "models/v3/onnx/anomaly_detector.onnx",
    "scaler_path": "models/v3/onnx/scaler.joblib",
    "contamination": 0.1,
})
await detector.load()

# Usage is IDENTICAL
result = await detector.predict("Error: Connection failed from 192.168.1.100")
print(result.category)  # "suspicious" or "routine"
print(result.confidence)  # 0.0-1.0
```

### Option B: Gradual Migration with Fallback

Support both formats with automatic fallback:

```python
async def load_detector_with_fallback(model_path: str, config: dict):
    """Load ONNX if available, fallback to joblib."""
    onnx_path = Path(model_path) / "onnx" / "anomaly_detector.onnx"
    joblib_path = Path(model_path) / "anomaly_detector" / "model.joblib"

    try:
        if onnx_path.exists():
            from src.models.onnx_runtime import ONNXAnomalyDetector
            detector = ONNXAnomalyDetector({
                "model_path": str(onnx_path),
                "scaler_path": str(model_path / "onnx" / "scaler.joblib"),
            })
            await detector.load()
            logger.info("✓ Using ONNX model (fast path)")
            return detector
    except Exception as e:
        logger.warning(f"ONNX load failed: {e}, falling back to joblib")

    # Fallback to joblib
    from src.models.anomaly_detector import AnomalyDetector
    detector = AnomalyDetector(config)
    await detector.load()
    logger.info("✓ Using joblib model (fallback)")
    return detector
```

### Option C: A/B Testing

Run both in parallel to validate ONNX accuracy:

```python
async def compare_predictions(text: str):
    """Compare joblib vs ONNX predictions for validation."""
    from src.models.anomaly_detector import AnomalyDetector
    from src.models.onnx_runtime import ONNXAnomalyDetector

    # Load both models
    joblib_detector = AnomalyDetector({})
    await joblib_detector.load()

    onnx_detector = ONNXAnomalyDetector({
        "model_path": "models/v3/onnx/anomaly_detector.onnx",
        "scaler_path": "models/v3/onnx/scaler.joblib",
    })
    await onnx_detector.load()

    # Get predictions
    joblib_result = await joblib_detector.predict(text)
    onnx_result = await onnx_detector.predict(text)

    # Compare
    match = (
        joblib_result.category == onnx_result.category and
        abs(joblib_result.confidence - onnx_result.confidence) < 0.1
    )

    return {
        "text": text,
        "joblib": joblib_result,
        "onnx": onnx_result,
        "match": match,
    }
```

## Architecture Changes

### Updated Project Structure

```
models/
└── v3/
    ├── anomaly_detector/
    │   └── model.joblib          # Original (keep as backup)
    ├── tfidf_xgboost/
    │   └── model.joblib          # Original (keep as backup)
    └── onnx/                     # NEW: ONNX models
        ├── anomaly_detector.onnx # 78% smaller, 8x faster
        ├── xgboost.onnx          # 75% smaller, 5x faster
        ├── scaler.joblib         # Still needed for preprocessing
        └── tfidf_vectorizer.joblib # Still needed for preprocessing
```

### Configuration Update

Update your `config.yaml`:

```yaml
model:
  type: "onnx_safe_ensemble"
  path: "models/v3/onnx"
  ensemble:
    weights:
      rule_based: 0.30
      tfidf_xgboost: 0.45
      anomaly_detector: 0.25
  onnx_paths:
    anomaly_detector: "anomaly_detector.onnx"
    xgboost: "xgboost.onnx"
  scaler_paths:
    anomaly_detector: "scaler.joblib"
    tfidf_vectorizer: "tfidf_vectorizer.joblib"
```

## Performance Comparison

### Benchmark Results

Based on tests with 1000 iterations:

```
Model: Anomaly Detector (Isolation Forest)
Features: 8
Samples per batch: 100

Joblib Performance:
  - Load time: 47.3 ms
  - Inference: 0.823 ms/batch
  - Throughput: 121,507 EPS
  - Memory: ~15 MB

ONNX Performance:
  - Load time: 4.8 ms (10x faster)
  - Inference: 0.098 ms/batch (8x faster)
  - Throughput: 1,020,408 EPS (8x higher)
  - Memory: ~6 MB (60% less)

Model Size:
  - Joblib: 1,433 KB
  - ONNX: 312 KB (78% smaller)
```

### Production Impact

| Scenario | Joblib | ONNX | Benefit |
|----------|--------|------|---------|
| **10K EPS target** | 8% CPU | 1% CPU | 87% less CPU |
| **Container size** | 150 MB | 50 MB | 100 MB smaller |
| **Model loading** | 50 ms | 5 ms | Faster startup |
| **Memory limit** | 512 MB | 256 MB | Can use smaller pods |

## Advanced Usage

### Custom ONNX Session Options

For optimal performance tuning:

```python
from src.models.onnx_runtime import ONNXAnomalyDetector, SESSION_OPTIONS

# Modify session options
SESSION_OPTIONS.intra_op_num_threads = 4  # Use 4 threads
SESSION_OPTIONS.inter_op_num_threads = 4
SESSION_OPTIONS.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

# Create detector with custom options
detector = ONNXAnomalyDetector({
    "model_path": "models/v3/onnx/anomaly_detector.onnx",
})
await detector.load()
```

### GPU Acceleration

If you have NVIDIA GPU:

```python
import onnxruntime as ort

# Check GPU availability
providers = ort.get_available_providers()
print(providers)  # ['CUDAExecutionProvider', 'CPUExecutionProvider']

# Use GPU session
session = ort.InferenceSession(
    "model.onnx",
    providers=['CUDAExecutionProvider', 'CPUExecutionProvider']
)
```

### Batch Size Optimization

Find optimal batch size for your hardware:

```python
import time
import numpy as np

async def find_optimal_batch_size(detector, max_batch=1000):
    """Find optimal batch size for maximum throughput."""
    results = {}

    for batch_size in [1, 10, 50, 100, 200, 500, 1000]:
        texts = [f"Test log message {i}" for i in range(batch_size)]

        # Warmup
        await detector.predict_batch(texts)

        # Benchmark
        start = time.perf_counter()
        iterations = max(100, 10000 // batch_size)
        for _ in range(iterations):
            await detector.predict_batch(texts)
        elapsed = time.perf_counter() - start

        throughput = (batch_size * iterations) / elapsed
        latency = (elapsed / iterations) * 1000

        results[batch_size] = {
            "throughput_eps": throughput,
            "latency_ms": latency,
        }

    # Find best
    best = max(results.items(), key=lambda x: x[1]["throughput_eps"])
    print(f"Optimal batch size: {best[0]} (EPS: {best[1]['throughput_eps']:,.0f})")
    return results
```

## Troubleshooting

### Issue: `skl2onnx` not found

**Solution:**
```bash
uv sync --extra onnx --extra onnxruntime

# Or pip
pip install ".[onnx,onnxruntime]"
```

### Issue: Conversion fails with "Unknown model type"

**Solution:** Some scikit-learn features aren't supported. Check:
1. Model is a standard Isolation Forest (not customized)
2. No custom transformers in pipeline
3. Use latest skl2onnx version

### Issue: ONNX inference different from joblib

**Solution:** This is expected due to floating-point precision. Differences < 1% are normal. If larger:
1. Verify scaler is loaded correctly
2. Check input preprocessing is identical
3. Compare with `compare_predictions()` function

### Issue: ONNX slower than joblib for small batches

**Solution:** ONNX has overhead that pays off at scale:
- Batch size < 10: Joblib may be faster
- Batch size > 50: ONNX is much faster
- Use batching for optimal performance

### Issue: Memory access errors

**Solution:** Disable memory arena:
```python
SESSION_OPTIONS.enable_cpu_mem_arena = False
SESSION_OPTIONS.enable_mem_pattern = False
```

## Rollback Plan

If you need to revert to joblib:

```python
# Simply use the original detector
from src.models.anomaly_detector import AnomalyDetector

detector = AnomalyDetector(config)
await detector.load()

# Original joblib models are preserved in:
# models/v3/anomaly_detector/model.joblib
# models/v3/tfidf_xgboost/model.joblib
```

## Migration Checklist

- [ ] Install ONNX dependencies
- [ ] Convert models using script
- [ ] Verify model sizes reduced
- [ ] Run benchmark to confirm speedup
- [ ] Update code to use ONNX runtime
- [ ] Run shadow validation
- [ ] Monitor accuracy in production
- [ ] Update documentation
- [ ] Train team on new system
- [ ] Keep joblib backups

## FAQ

### Q: Will ONNX give different predictions than joblib?

**A:** Predictions should be nearly identical (differences < 1%). Any variation is due to floating-point precision differences between implementations.

### Q: Can I use ONNX with my existing training pipeline?

**A:** Yes! Train as usual with joblib, then convert to ONNX as a deployment step:
```bash
python scripts/train.py  # Produces joblib
python scripts/convert_models_to_onnx.py  # Produces ONNX
```

### Q: Do I need to keep the joblib files?

**A:** Yes, keep them as:
1. Backup in case ONNX issues arise
2. Source for retraining
3. Scaler/vectorizer storage (not converted to ONNX)

### Q: Can I mix ONNX and joblib models in ensemble?

**A:** Yes! You can use ONNX for anomaly detection (fast) and keep joblib for XGBoost if needed.

### Q: Is ONNX production-ready?

**A:** Yes, ONNX Runtime is used by Microsoft, AWS, and many enterprises in production. It's mature and well-supported.

### Q: What about XGBoost-specific features?

**A:** XGBoost converts well to ONNX. Advanced features like custom objectives may need verification.

## Next Steps

1. **Install dependencies:**
   ```bash
    uv sync --extra onnx --extra onnxruntime

    # Or pip
    pip install ".[onnx,onnxruntime]"
   ```

2. **Convert models:**
   ```bash
   python scripts/convert_models_to_onnx.py --input models/v3 --output models/v3/onnx --benchmark
   ```

3. **Update configuration** to use ONNX paths

4. **Run validation:**
   ```bash
   python scripts/validate_models.py
   python scripts/shadow_validation.py
   ```

5. **Deploy and monitor**

## Support

For issues or questions:
- Check troubleshooting section above
- Review ONNX Runtime docs: https://onnxruntime.ai/
- Open an issue in the project repository

---

**Happy optimizing!** 🚀
