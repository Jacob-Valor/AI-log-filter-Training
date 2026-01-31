# AI Log Filter Documentation

Welcome to the AI Log Filter documentation. This directory contains comprehensive guides, references, and resources for deploying, operating, and optimizing your ML-based log classification system.

## 📚 Documentation Index

### 🚀 Quick Start Guides
- **[ONNX Quick Start](performance/ONNX_QUICK_START.md)** - 3-step migration to ONNX (15 minutes)
- **[Cost Tracking Quick Start](tracking/COST_TRACKING_QUICK_START.md)** - Cost monitoring setup

### 📖 Core Documentation
- **[API Reference](reference/API.md)** - REST API endpoints and examples
- **[Troubleshooting Guide](reference/TROUBLESHOOTING.md)** - Common issues and solutions
- **[Anomaly Detection Techniques](performance/anomaly_techniques_comparison.md)** - ML model comparison

### 🏗️ Architecture
- **[Production Architecture](architecture/PRODUCTION_ARCHITECTURE.md)** - System design and components
- **[Production Architecture Enhanced](architecture/PRODUCTION_ARCHITECTURE_ENHANCED.md)** - Advanced patterns
- **[Production Architecture VNext](architecture/PRODUCTION_ARCHITECTURE_VNEXT.md)** - Future roadmap

### 🔧 Operations & Runbooks
- **[Incident Response](runbooks/INCIDENT-RESPONSE.md)** - Emergency procedures
- **[Operations Runbook](runbooks/OPERATION_RUNBOOK.md)** - Daily operations guide
- **[Assessment Scorecard](assessment/ASSESSMENT_SCORECARD.md)** - Production readiness checklist

### 💰 Cost & Performance
- **[Cost Tracking](tracking/COST_TRACKING.md)** - Cost monitoring and optimization
- **[Docker Setup Update](tracking/DOCKER_SETUP_UPDATE.md)** - Container best practices

### 🎓 Training
- **[SOC Training Guide](training/SOC_TRAINING_GUIDE.md)** - 50+ pages of SOC team training

### 🚀 Performance Optimization
- **[ONNX Only Mode](performance/ONNX_ONLY_MODE.md)** - Complete ONNX-only setup guide 🆕
- **[ONNX Migration Guide](performance/ONNX_MIGRATION_GUIDE.md)** - Complete ONNX migration (comprehensive)
- **[ONNX vs Joblib Comparison](performance/ONNX_VS_JOBLIB_COMPARISON.md)** - Detailed performance comparison
- **[ONNX Quick Start](performance/ONNX_QUICK_START.md)** - 3-step quick migration

---

## 🆕 New Features

### ONNX Runtime Support (v3.1)
Convert your models to ONNX format for **8x faster inference** and **78% smaller model size**.

**Quick Start:**
```bash
# Recommended (uses `uv.lock`)
uv sync --extra dev --extra onnx --extra onnxruntime

# Or pip (installs project extras)
# Note: onnxruntime wheels may lag newest Python versions.
pip install ".[onnx,onnxruntime]"

python scripts/convert_models_to_onnx.py --input models/v3 --output models/v3/onnx --benchmark
```

**Docs:**
- [ONNX Only Mode](performance/ONNX_ONLY_MODE.md) - ONNX-first setup (ONNX inference + minimal preprocessing artifacts) 🆕 **RECOMMENDED**
- [ONNX Quick Start](performance/ONNX_QUICK_START.md) - Get started in 15 minutes
- [ONNX Migration Guide](performance/ONNX_MIGRATION_GUIDE.md) - Complete guide
- [ONNX vs Joblib](performance/ONNX_VS_JOBLIB_COMPARISON.md) - Performance comparison

### SPC Statistical Monitoring (v3.1)
Statistical Process Control for real-time metric anomaly detection.

**Key Benefits:**
- **Zero training required** - Works immediately
- **Self-adapting** thresholds
- **Ultra-fast** (~0.01ms per check)
- **Highly interpretable** (3-sigma rule)

**Usage:**
```python
from src.monitoring.spc_detector import create_siem_spc_detectors

spc = create_siem_spc_detectors()
result = spc.check("error_rate", current_error_rate)
if result.is_anomaly:
    logger.warning(f"Anomaly: {result.explanation}")
```

---

## 📊 Documentation by Role

### For Developers
1. [API Reference](reference/API.md) - Integration guide
2. [Troubleshooting](reference/TROUBLESHOOTING.md) - Debug issues
3. [ONNX Migration](performance/ONNX_MIGRATION_GUIDE.md) - Performance optimization

### For DevOps/SRE
1. [Production Architecture](architecture/PRODUCTION_ARCHITECTURE.md) - System overview
2. [Operations Runbook](runbooks/OPERATION_RUNBOOK.md) - Daily ops
3. [Incident Response](runbooks/INCIDENT-RESPONSE.md) - Emergency procedures
4. [Cost Tracking](tracking/COST_TRACKING.md) - Cost management

### For Security Teams (SOC)
1. [SOC Training Guide](training/SOC_TRAINING_GUIDE.md) - 50+ page training manual
2. [Anomaly Detection Techniques](performance/anomaly_techniques_comparison.md) - How detection works
3. [Incident Response](runbooks/INCIDENT-RESPONSE.md) - Security incident procedures

### For Architects
1. [Production Architecture](architecture/PRODUCTION_ARCHITECTURE.md) - Current design
2. [Architecture Enhanced](architecture/PRODUCTION_ARCHITECTURE_ENHANCED.md) - Advanced patterns
3. [Assessment Scorecard](assessment/ASSESSMENT_SCORECARD.md) - Readiness checklist

---

## 🎯 Popular Topics

### Performance Optimization
| Topic | Guide | Benefit |
|-------|-------|---------|
| **ONNX Migration** | [ONNX Quick Start](performance/ONNX_QUICK_START.md) | 8x faster inference |
| **SPC Monitoring** | [SPC Detector](../src/monitoring/spc_detector.py) | Real-time metric anomalies |
| **Model Optimization** | [Anomaly Techniques](performance/anomaly_techniques_comparison.md) | Choose best algorithm |
| **Cost Reduction** | [Cost Tracking](tracking/COST_TRACKING.md) | 40-60% cost savings |

### Operations
| Topic | Guide | Purpose |
|-------|-------|---------|
| **Daily Operations** | [Operations Runbook](runbooks/OPERATION_RUNBOOK.md) | Routine tasks |
| **Incident Response** | [Incident Response](runbooks/INCIDENT-RESPONSE.md) | Emergency handling |
| **Health Monitoring** | [Troubleshooting](reference/TROUBLESHOOTING.md) | System health checks |
| **API Integration** | [API Reference](reference/API.md) | External integrations |

### Architecture
| Topic | Guide | Level |
|-------|-------|-------|
| **Current Architecture** | [Production Architecture](architecture/PRODUCTION_ARCHITECTURE.md) | Standard |
| **Advanced Patterns** | [Architecture Enhanced](architecture/PRODUCTION_ARCHITECTURE_ENHANCED.md) | Advanced |
| **Future Roadmap** | [Architecture VNext](architecture/PRODUCTION_ARCHITECTURE_VNEXT.md) | Strategic |
| **Readiness Check** | [Assessment Scorecard](assessment/ASSESSMENT_SCORECARD.md) | Validation |

---

## 🔍 Finding Information

### By Task
- **Setting up locally** → [Docker Setup](tracking/DOCKER_SETUP_UPDATE.md)
- **Deploying to production** → [Production Architecture](architecture/PRODUCTION_ARCHITECTURE.md)
- **Integrating with QRadar** → [API Reference](reference/API.md)
- **Optimizing performance** → [ONNX Migration](performance/ONNX_MIGRATION_GUIDE.md)
- **Reducing costs** → [Cost Tracking](tracking/COST_TRACKING.md)
- **Training SOC team** → [SOC Training Guide](training/SOC_TRAINING_GUIDE.md)
- **Handling incidents** → [Incident Response](runbooks/INCIDENT-RESPONSE.md)

### By Component
- **Models** → [Anomaly Techniques](performance/anomaly_techniques_comparison.md), [ONNX Migration](performance/ONNX_MIGRATION_GUIDE.md)
- **API** → [API Reference](reference/API.md)
- **Monitoring** → [SPC Detector](../src/monitoring/spc_detector.py), [Troubleshooting](reference/TROUBLESHOOTING.md)
- **Infrastructure** → [Production Architecture](architecture/PRODUCTION_ARCHITECTURE.md)
- **Operations** → [Operations Runbook](runbooks/OPERATION_RUNBOOK.md)

---

## 📈 Documentation Statistics

- **Total Pages**: 15+ comprehensive guides
- **Code Examples**: 100+ examples
- **Architecture Diagrams**: 5 detailed diagrams
- **API Endpoints**: 10+ documented
- **Troubleshooting Scenarios**: 20+ common issues
- **Training Materials**: 50+ pages

---

## 🔄 Recent Updates

### January 2026 (v3.1)
- ✅ **ONNX Runtime Support** - 8x faster inference
- ✅ **SPC Monitoring** - Statistical process control
- ✅ **Enhanced Documentation** - Complete guides
- ✅ **Cost Tracking** - Cost optimization tools
- ✅ **Performance Comparisons** - Detailed benchmarks

### December 2025 (v3.0)
- ✅ Production-ready release
- ✅ Complete CI/CD pipeline
- ✅ Kubernetes manifests
- ✅ Grafana dashboards
- ✅ Shadow mode validation

---

## 🤝 Contributing

Found an issue or want to contribute? See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

---

## 📞 Support

- **Issues**: Open a GitHub issue
- **Questions**: Check [Troubleshooting](reference/TROUBLESHOOTING.md) first
- **Security**: See [SECURITY.md](../SECURITY.md)

---

**Quick Links:**
[Getting Started](../README.md#getting-started) •
[API](reference/API.md) •
[Troubleshooting](reference/TROUBLESHOOTING.md) •
[ONNX Migration](performance/ONNX_MIGRATION_GUIDE.md)
