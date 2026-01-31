# Anomaly Detection Techniques Comparison

[Back to docs index](../README.md) • [Performance index](README.md)

## Executive Summary

Your current **Isolation Forest** implementation is well-suited for production SIEM use. This document compares alternatives and provides guidance on when each technique excels.

---

## Quick Decision Matrix

| If You Need... | Use This | Your Current Status |
|----------------|----------|---------------------|
| **Maximum speed** (< 1ms) | SPC (Statistical) | ✅ Can add easily |
| **Sequential pattern detection** | LSTM Autoencoder | Consider for v2 |
| **Semantic understanding** | BERT/Transformers | Not recommended for real-time |
| **Production reliability** | Isolation Forest | ✅ Already implemented |
| **Zero training** | SPC or Rule-based | ✅ Can add SPC today |
| **Best accuracy** | Ensemble of all | Future enhancement |

---

## Detailed Technique Comparison

### 1. Isolation Forest (Your Current Implementation)

**How It Works:**
- Randomly partitions data space
- Anomalies isolated faster (shorter tree paths)
- Averages across multiple trees (forest)

**Pros:**
- ✅ Fast inference (~1ms per log)
- ✅ No distribution assumptions
- ✅ Handles high-dimensional data
- ✅ Unsupervised (no labels needed)
- ✅ Interpretable anomaly scores
- ✅ Proven in production

**Cons:**
- ❌ Doesn't capture sequential patterns
- ❌ Static after training
- ❌ Can miss subtle context

**Best For:**
- Production SIEM with 10K+ EPS
- Real-time classification
- Feature-based anomaly detection

**Your Score:** ⭐⭐⭐⭐⭐ (Excellent choice)

---

### 2. Statistical Process Control (SPC)

**How It Works:**
- Tracks metrics over time
- Uses control charts (3-sigma rule)
- Flags deviations from normal range

**Pros:**
- ✅ **Zero training required**
- ✅ **Fastest** (~0.01ms per check)
- ✅ **Self-adapting** to new patterns
- ✅ **Highly interpretable** (z-scores)
- ✅ Industry-proven (100+ years)
- ✅ Detects trends and drift

**Cons:**
- ❌ Only for numerical metrics (not text)
- ❌ Needs continuous metric stream
- ❌ Sensitive to sudden baseline changes

**Best For:**
- System health monitoring (EPS, error rates)
- Time-series metrics
- Quick deployment without training

**Recommended Addition:** ⭐⭐⭐⭐⭐ (Add today)

**Implementation:**
```python
from src.monitoring.spc_detector import create_siem_spc_detectors

# Create detectors
spc = create_siem_spc_detectors()

# In your processing loop:
result = spc.check("error_rate", current_error_rate)
if result.is_anomaly:
    logger.warning(f"Anomaly: {result.explanation}")
```

---

### 3. LSTM Autoencoder

**How It Works:**
- Neural network learns to reconstruct normal sequences
- High reconstruction error = anomaly
- Captures temporal dependencies

**Pros:**
- ✅ **Sequential pattern detection**
- ✅ Captures long-term dependencies
- ✅ State-of-the-art for time-series
- ✅ Can model complex relationships

**Cons:**
- ❌ **10-50x slower** (~20-50ms)
- ❌ Requires GPU for training
- ❌ Needs large training dataset (100K+ sequences)
- ❌ Complex hyperparameter tuning
- ❌ Black box (hard to interpret)
- ❌ High maintenance

**Best For:**
- Multi-step attack detection
- Session-based analysis
- Offline batch processing

**Verdict:** ⭐⭐⭐ (Consider for v2, not primary)

---

### 4. Transformer (BERT-based)

**How It Works:**
- Pre-trained language model
- Fine-tuned on log data
- Understands semantic meaning

**Pros:**
- ✅ **Semantic understanding**
- ✅ Transfer learning (pre-trained)
- ✅ Handles similar phrases consistently
- ✅ Context-aware

**Cons:**
- ❌ **100-500x slower** (~100-500ms)
- ❌ Requires GPU infrastructure
- ❌ High compute costs at scale
- ❌ Large model size (400MB-1.5GB)
- ❌ Complex deployment
- ❌ Overkill for most log classification

**Best For:**
- Offline analysis
- Model validation (sample 1% of logs)
- Research/experimentation

**Verdict:** ⭐⭐ (Not for real-time SIEM)

---

### 5. Local Outlier Factor (LOF)

**How It Works:**
- Density-based anomaly detection
- Compares local density to neighbors
- Lower density = anomaly

**Pros:**
- ✅ Good for clustered data
- ✅ No distribution assumptions
- ✅ Handles local anomalies
- ✅ Better than Isolation Forest for some patterns

**Cons:**
- ❌ Slower than Isolation Forest
- ❌ Memory intensive (stores all points)
- ❌ Sensitive to parameter choice
- ❌ Doesn't scale well

**Best For:**
- Small to medium datasets
- Clustered data with local anomalies
- Batch processing (not streaming)

**Verdict:** ⭐⭐⭐ (Alternative, not necessarily better)

---

### 6. One-Class SVM

**How It Works:**
- Learns boundary around normal data
- Points outside boundary = anomalies
- Kernel trick for non-linear boundaries

**Pros:**
- ✅ Well-studied algorithm
- ✅ Flexible kernels
- ✅ Good for small datasets

**Cons:**
- ❌ Slow training
- ❌ Sensitive to parameters
- ❌ Doesn't scale to large data
- ❌ Harder to interpret than Isolation Forest

**Verdict:** ⭐⭐ (Legacy choice, Isolation Forest is better)

---

## Recommendation for Your SIEM

### Immediate Actions (This Week)

1. **Add SPC Monitoring** (5 minutes to implement)
   ```python
   # Add to your monitoring
   spc_manager = create_siem_spc_detectors()
   
   # Track these metrics:
   # - EPS (events per second)
   # - Error rate
   # - Processing latency
   # - Failed login rate
   ```

2. **Benefits:**
   - Detect system-level anomalies immediately
   - Zero training required
   - Self-adapting to traffic patterns
   - Alerts on DDoS, system failures, etc.

### Short-term (Next Month)

3. **Consider LSTM for Session Analysis**
   - Process login sessions in batches
   - Detect multi-step attacks
   - Flag suspicious sequences
   - Keep real-time path as Isolation Forest

### Long-term (Next Quarter)

4. **Hierarchical Ensemble**
   ```
   Layer 1 (100% of logs):
   ├── Rule-based (instant)
   └── SPC (instant)
   
   Layer 2 (50% flagged):
   ├── Isolation Forest (fast)
   └── LOF (fast)
   
   Layer 3 (5% suspicious):
   ├── LSTM (batch)
   └── BERT (sample)
   ```

---

## Performance Comparison

| Technique | Latency | Throughput | Model Size | Training Time | Accuracy |
|-----------|---------|------------|------------|---------------|----------|
| **Isolation Forest** | ~1ms | 10K+ EPS | 1.4MB | Minutes | ⭐⭐⭐⭐ |
| **SPC** | ~0.01ms | 1M+ EPS | <1KB | None | ⭐⭐⭐ |
| **LSTM** | ~50ms | 200 EPS | 100MB | Hours+GPU | ⭐⭐⭐⭐⭐ |
| **BERT** | ~200ms | 50 EPS | 500MB | Hours+GPU | ⭐⭐⭐⭐⭐ |
| **One-Class SVM** | ~5ms | 2K EPS | 10MB | Hours | ⭐⭐⭐ |
| **LOF** | ~3ms | 5K EPS | In-memory | Minutes | ⭐⭐⭐⭐ |

---

## When Is Each "Better"?

### Isolation Forest is better when:
- You need real-time processing (10K+ EPS)
- You have limited compute resources
- You want unsupervised learning
- You need interpretable results
- You're building a production SIEM

### SPC is better when:
- You need immediate deployment (no training)
- You're monitoring numerical metrics
- You want self-adapting thresholds
- You need trend detection
- You want industry-standard interpretability

### LSTM is better when:
- You have GPU resources
- Sequential patterns matter
- You can do batch processing
- You have 100K+ training sequences
- You need state-of-the-art accuracy

### BERT is better when:
- You have GPU infrastructure
- Semantic understanding is critical
- You can sample logs (not all)
- You need transfer learning
- You have ML engineering resources

---

## Implementation Priority

```
Priority 1 (Do Now): ✅
├── Keep Isolation Forest (already implemented)
└── Add SPC monitoring (src/monitoring/spc_detector.py created)

Priority 2 (Next Month): 📅
├── LSTM for session batch processing
└── Graph analysis for workflow paths

Priority 3 (Next Quarter): 🔮
├── Hierarchical ensemble
├── BERT for validation sampling
└── Advanced feature engineering
```

---

## Conclusion

**Your current Isolation Forest is NOT inferior.** It's actually an excellent choice for production SIEM with your 10K EPS target.

**"Better" depends on your definition:**
- **Speed:** SPC wins
- **Accuracy:** LSTM/Transformer win
- **Production reliability:** Isolation Forest wins
- **Ease of deployment:** SPC wins
- **Overall for SIEM:** **Ensemble approach wins**

**Recommendation:**
1. Keep Isolation Forest as your primary classifier (25% weight in ensemble)
2. Add SPC for system metric monitoring (immediate value)
3. Consider LSTM for offline session analysis (future enhancement)
4. Don't use BERT for real-time (overkill)

Your current system is **production-ready**. The SPC addition will make it **even better** with minimal effort.

---

## References

- Liu, F. T., et al. (2008). Isolation Forest. ICDM.
- Hochreiter, S., & Schmidhuber, J. (1997). LSTM. Neural Computation.
- Devlin, J., et al. (2018). BERT. NAACL.
- Shewhart, W. A. (1931). Economic Control of Quality.
