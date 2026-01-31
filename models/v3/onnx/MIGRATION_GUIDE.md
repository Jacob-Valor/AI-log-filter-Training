# ONNX Migration Guide

## Overview

Your models have been converted to ONNX format for faster inference and smaller size.

## Changes

### 1. Model Files
- Old: `models/v3/anomaly_detector/model.joblib` (~1.4 MB)
- New: `models/v3/onnx/anomaly_detector.onnx` (~300 KB)

### 2. Code Changes

Replace:
```python
from src.models.anomaly_detector import AnomalyDetector
detector = AnomalyDetector(config)
await detector.load()
```

With:
```python
from src.models.onnx_runtime import ONNXAnomalyDetector
detector = ONNXAnomalyDetector({
    "model_path": "models/v3/onnx/anomaly_detector.onnx",
    "scaler_path": "models/v3/onnx/scaler.joblib",
})
await detector.load()
```

### 3. Dependencies

Add to requirements.txt:
```
# ONNX Runtime (choose one)
onnxruntime>=1.17.0        # CPU version (recommended)
# onnxruntime-gpu>=1.17.0  # GPU version (if you have GPU)
```

## Benefits

- **2-10x faster inference**
- **70-80% smaller model size**
- **Lower memory usage**
- **Cross-platform compatibility**

## Rollback

If needed, you can always use the original joblib models:
```python
from src.models.anomaly_detector import AnomalyDetector  # Still works!
```

## Testing

Run validation:
```bash
python scripts/validate_models.py
python scripts/shadow_validation.py
```
