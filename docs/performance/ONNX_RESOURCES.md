# ONNX Resources - Complete Index

[Back to docs index](../README.md) • [Performance index](README.md)

All ONNX-related documentation and code in one place.

## 🚀 Getting Started (Choose Your Path)

### Path 1: Quick Migration (15 minutes)
**For:** Those who want to try ONNX without major changes
- 📄 [ONNX Quick Start](ONNX_QUICK_START.md) - 3-step guide
- 📄 [ONNX Migration Guide](ONNX_MIGRATION_GUIDE.md) - Complete guide

### Path 2: ONNX-Only Mode (Recommended for Production)
**For:** Those who want maximum performance with no joblib at runtime
- 📄 [ONNX Only Mode](ONNX_ONLY_MODE.md) - Complete setup guide
- 💻 [Example](../../examples/onnx_only_example.py) - Working example
- 🔧 [ONNX Ensemble](../../src/models/onnx_ensemble.py) - ONNX-only classifier

### Path 3: Comparison & Decision Making
**For:** Those deciding whether to migrate
- 📄 [ONNX vs Joblib](ONNX_VS_JOBLIB_COMPARISON.md) - Detailed comparison
- 📄 [Anomaly Techniques](anomaly_techniques_comparison.md) - Algorithm comparison

---

## 📚 Documentation

### Quick References
| Document | Purpose | Time |
|----------|---------|------|
| [ONNX Quick Start](ONNX_QUICK_START.md) | Get started fast | 15 min |
| [ONNX Only Mode](ONNX_ONLY_MODE.md) | Complete ONNX setup | 30 min |
| [ONNX Migration Guide](ONNX_MIGRATION_GUIDE.md) | Full migration | 1 hour |
| [ONNX vs Joblib](ONNX_VS_JOBLIB_COMPARISON.md) | Decision making | 20 min |

### In-Depth Guides
| Document | Purpose | Audience |
|----------|---------|----------|
| [ONNX Migration Guide](ONNX_MIGRATION_GUIDE.md) | Complete migration | Developers |
| [ONNX Only Mode](ONNX_ONLY_MODE.md) | Production setup | DevOps/SRE |
| [API](../reference/API.md) | Current HTTP endpoints | Integrators |
| [Troubleshooting](../reference/TROUBLESHOOTING.md) | ONNX issues | All |

---

## 💻 Source Code

### Core ONNX Modules
| Module | Purpose | Location |
|--------|---------|----------|
| `onnx_runtime.py` | ONNX inference wrapper | `src/models/onnx_runtime.py` |
| `onnx_ensemble.py` | ONNX-only ensemble | `src/models/onnx_ensemble.py` |
| `onnx_converter.py` | Model conversion | `src/models/onnx_converter.py` |
| `onnx_config.py` | ONNX configuration | `src/utils/onnx_config.py` |

### Usage Examples
```python
# Example 1: ONNX-only classifier (recommended)
from src.models.onnx_ensemble import create_onnx_classifier

classifier = await create_onnx_classifier("models/v3/onnx")
results = await classifier.classify_batch(logs)
```

```python
# Example 2: Individual ONNX detector
from src.models.onnx_runtime import ONNXAnomalyDetector

detector = ONNXAnomalyDetector({
    "model_path": "models/v3/onnx/anomaly_detector.onnx",
    "scaler_path": "models/v3/onnx/scaler.joblib",
})
await detector.load()
result = await detector.predict(log_text)
```

```python
# Example 3: Validate ONNX setup
from src.utils.onnx_config import validate_onnx_setup, print_onnx_validation

is_valid = validate_onnx_setup("models/v3/onnx")
print_onnx_validation("models/v3/onnx")  # Pretty print
```

---

## 🔧 Scripts & Tools

### Conversion Script
```bash
# Convert all models
python scripts/convert_models_to_onnx.py \
    --input models/v3 \
    --output models/v3/onnx \
    --benchmark
```

### Validation Script
```bash
# Validate ONNX setup
python -c "
from src.utils.onnx_config import print_onnx_validation
print_onnx_validation('models/v3/onnx')
"
```

### Example Script
```bash
# Run ONNX-only example
python examples/onnx_only_example.py
```

---

## 🎯 Configuration

### ONNX-Only Config
```yaml
model:
  type: "onnx_safe_ensemble"
  path: "models/v3/onnx"
  
  onnx_paths:
    anomaly_detector: "anomaly_detector.onnx"
    xgboost: "xgboost.onnx"
```

### Environment Variables
```bash
export MODEL_PATH=models/v3/onnx
export MODEL_TYPE=onnx_safe_ensemble
```

---

## 📊 Performance Metrics

### Expected Improvements
| Metric | Joblib | ONNX | Improvement |
|--------|--------|------|-------------|
| Inference | 0.82 ms | 0.10 ms | **8x** |
| Model Size | 1.43 MB | 0.31 MB | **78%** |
| Memory | 15 MB | 6 MB | **60%** |
| Load Time | 47 ms | 5 ms | **90%** |

### Benchmarking
```python
from src.models.onnx_runtime import compare_inference_speed

results = compare_inference_speed(
    joblib_detector=old_detector,
    onnx_detector=new_detector,
    test_texts=test_logs,
    iterations=100
)

print(f"Speedup: {results['speedup']:.2f}x")
```

---

## 🐳 Docker & Kubernetes

### Dockerfile (ONNX-Only)
```dockerfile
FROM python:3.13-slim

# Install only ONNX runtime
RUN pip install onnxruntime numpy fastapi uvicorn

# Copy ONNX models (not joblib)
COPY models/v3/onnx /app/models/

ENV MODEL_PATH=/app/models
ENV MODEL_TYPE=onnx_safe_ensemble
```

### Kubernetes (Reduced Resources)
```yaml
resources:
  requests:
    memory: "128Mi"  # Was 512Mi
    cpu: "100m"      # Was 500m
  limits:
    memory: "256Mi"  # Was 1Gi
    cpu: "500m"      # Was 2000m
```

---

## ❓ FAQ - Common Questions

**Q: Can I use ONNX and joblib together?**
A: Yes, use `SafeEnsembleClassifier` for mixed mode, or `ONNXSafeEnsembleClassifier` for ONNX-only.

**Q: Do I need to keep joblib files?**
A: For ONNX-only: Keep only scalers/vectorizers (preprocessing). For training: Keep all joblib files.

**Q: Is ONNX slower for small batches?**
A: Yes (<10 items), but much faster at scale (>50 items). Always use batching.

**Q: Can I use GPU with ONNX?**
A: Yes! Install `onnxruntime-gpu` and set providers to `['CUDAExecutionProvider']`.

**Q: What if conversion fails?**
A: Check [Troubleshooting](../reference/TROUBLESHOOTING.md) (ONNX section).

---

## 🔗 Quick Links

**Start Here:**
- [ONNX Quick Start](ONNX_QUICK_START.md) ⭐
- [ONNX Only Mode](ONNX_ONLY_MODE.md) ⭐⭐

**Reference:**
- [ONNX Migration Guide](ONNX_MIGRATION_GUIDE.md)
- [ONNX vs Joblib](ONNX_VS_JOBLIB_COMPARISON.md)
- [API](../reference/API.md)

**Support:**
- [Troubleshooting](../reference/TROUBLESHOOTING.md)
- Example: [onnx_only_example.py](../../examples/onnx_only_example.py)

---

## ✅ Migration Checklist

- [ ] Install ONNX dependencies
- [ ] Convert models: `scripts/convert_models_to_onnx.py`
- [ ] Validate setup: `print_onnx_validation()`
- [ ] Update code to use `create_onnx_classifier()`
- [ ] Test locally
- [ ] Run shadow validation
- [ ] Update Docker (smaller images)
- [ ] Update Kubernetes (lower resources)
- [ ] Deploy to production
- [ ] Monitor performance metrics

---

**Need Help?** See [Troubleshooting](../reference/TROUBLESHOOTING.md) or open an issue.

**Ready to Start?** → [ONNX Quick Start](ONNX_QUICK_START.md)
