# Contributing to AI-Driven Log Filtering for SIEM

Thank you for your interest in contributing! This document provides guidelines for contributing to this project.

## 🚀 Quick Start

```bash
# 1. Fork the repository on GitHub

# 2. Clone your fork
git clone https://github.com/YOUR_USERNAME/AI-log-filter-Training.git
cd AI-log-filter-Training

# 3. Create a branch
git checkout -b feature/your-feature-name

# 4. Set up development environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# 5. Make your changes and test
pytest tests/ -v

# 6. Commit and push
git add .
git commit -m "feat(scope): description"
git push origin feature/your-feature-name

# 7. Open a Pull Request on GitHub
```

## 📋 Development Setup

### Prerequisites

| Requirement | Version    |
|-------------|------------|
| Python      | 3.13+      |
| pip         | Latest     |
| Git         | 2.x        |
| Docker      | Optional   |

### Environment Setup

```bash
# Option A: pip (traditional)
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Option B: uv (recommended - faster)
pip install uv
uv sync --extra dev

# Option C: Docker
docker build -t ai-log-filter-dev .
docker run -it ai-log-filter-dev bash
```

### Verify Setup

```bash
# Run linter
ruff check src/ tests/

# Run tests
pytest tests/ -v

# Validate models
python scripts/validate_models.py
```

## 🔧 Code Style

We use **Ruff** for linting and formatting, configured in `pyproject.toml`.

### Formatting

```bash
# Format all code
ruff format src/ tests/ scripts/

# Check formatting without changes
ruff format --check src/ tests/
```

### Linting

```bash
# Check for issues
ruff check src/ tests/

# Auto-fix issues
ruff check src/ tests/ --fix
```

### Code Standards

| Standard              | Requirement                          |
|-----------------------|--------------------------------------|
| **Type hints**        | Required for all public functions    |
| **Docstrings**        | Google-style for modules/classes/functions |
| **Line length**       | Max 100 characters                   |
| **Imports**           | Sorted with isort (via Ruff)         |
| **Quotes**            | Double quotes preferred              |

### Example Code

```python
"""Module description goes here."""

from typing import Any


class ExampleClass:
    """Example class with proper documentation.
    
    Args:
        name: The name of the example.
        config: Configuration dictionary.
    
    Attributes:
        name: The name of the example.
    """
    
    def __init__(self, name: str, config: dict[str, Any] | None = None) -> None:
        self.name = name
        self.config = config or {}
    
    def process(self, data: list[str]) -> dict[str, Any]:
        """Process the input data.
        
        Args:
            data: List of strings to process.
        
        Returns:
            Dictionary containing processed results.
        
        Raises:
            ValueError: If data is empty.
        """
        if not data:
            raise ValueError("Data cannot be empty")
        
        return {"processed": len(data)}
```

## 📝 Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): description

[optional body]

[optional footer]
```

### Types

| Type       | Description                              |
|------------|------------------------------------------|
| `feat`     | New feature                              |
| `fix`      | Bug fix                                  |
| `docs`     | Documentation changes                    |
| `style`    | Code style changes (formatting)          |
| `refactor` | Code refactoring                         |
| `test`     | Adding/updating tests                    |
| `chore`    | Maintenance tasks                        |
| `perf`     | Performance improvements                 |
| `ci`       | CI/CD changes                            |
| `security` | Security improvements                    |

### Examples

```
feat(models): add isolation forest anomaly detector

- Implement IsolationForest-based anomaly detection
- Add configuration for contamination parameter
- Include unit tests and documentation

Closes #123
```

```
fix(kafka): resolve consumer lag issue on restart

The consumer was not properly committing offsets on shutdown,
causing reprocessing of messages. This fix ensures proper
offset commitment during graceful shutdown.

Fixes #456
```

## 🧪 Testing Requirements

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html --cov-report=term-missing

# Run specific test file
pytest tests/test_circuit_breaker.py -v

# Run tests matching pattern
pytest tests/ -k "test_classify" -v

# Run integration tests (requires Kafka)
pytest tests/ -m integration -v
```

### Test Requirements

| Requirement               | Standard                    |
|---------------------------|----------------------------|
| New features              | Must have tests             |
| Bug fixes                 | Must have regression tests  |
| Code coverage             | Maintain or improve         |
| Test naming               | `test_<function>_<scenario>` |
| Test isolation            | Each test must be independent |

### Test Structure

```python
"""Tests for example module."""

import pytest

from src.example import ExampleClass


class TestExampleClass:
    """Tests for ExampleClass."""
    
    @pytest.fixture
    def example_instance(self) -> ExampleClass:
        """Create example instance for testing."""
        return ExampleClass(name="test")
    
    def test_process_with_valid_data_returns_results(
        self, example_instance: ExampleClass
    ) -> None:
        """Test process with valid input data."""
        result = example_instance.process(["a", "b", "c"])
        
        assert result["processed"] == 3
    
    def test_process_with_empty_data_raises_error(
        self, example_instance: ExampleClass
    ) -> None:
        """Test process with empty data raises ValueError."""
        with pytest.raises(ValueError, match="Data cannot be empty"):
            example_instance.process([])
```

## 🛡️ Security Considerations

### Critical Safety Requirements

This project processes security logs. **All changes must maintain:**

| Requirement              | Description                                |
|--------------------------|--------------------------------------------|
| **Fail-open behavior**   | Errors must forward all logs to QRadar     |
| **Compliance bypass**    | Regulated logs must bypass AI filtering    |
| **Audit trail**          | All classifications must be logged         |
| **Zero data loss**       | No logs can be dropped                     |

### Before Submitting

- [ ] Changes maintain fail-open behavior
- [ ] Compliance bypass logic preserved (PCI/HIPAA/SOX/GDPR)
- [ ] No sensitive data in logs or errors
- [ ] Circuit breaker integration maintained
- [ ] Rate limiting not bypassed

### Security Review

Changes affecting these areas require additional security review:

- `src/preprocessing/compliance_gate.py`
- `src/utils/circuit_breaker.py`
- `src/api/rate_limiter.py`
- Authentication/authorization logic
- Data handling/processing

## 📤 Pull Request Process

### Before Creating PR

1. **Update from main**
   ```bash
   git fetch origin
   git rebase origin/main
   ```

2. **Run all checks**
   ```bash
   ruff check src/ tests/
   ruff format --check src/ tests/
   pytest tests/ -v --cov=src
   ```

3. **Update documentation**
   - Update README.md if needed
   - Update API docs for new endpoints
   - Add inline comments for complex logic

### PR Checklist

- [ ] Code follows style guidelines
- [ ] All tests pass
- [ ] New tests added for new functionality
- [ ] Documentation updated
- [ ] Commit messages follow convention
- [ ] PR description is complete
- [ ] No merge conflicts

### Review Process

1. Automated checks must pass (lint, test, security)
2. At least 1 approval required
3. CODEOWNERS review for their areas
4. Resolve all conversations before merge
5. Squash and merge to main

## 🐛 Reporting Issues

### Bug Reports

Use the [Bug Report Template](/.github/ISSUE_TEMPLATE/bug_report.md) and include:

- Python version (`python --version`)
- Operating system
- Steps to reproduce
- Expected vs actual behavior
- Relevant logs or error messages
- Minimal reproducible example

### Security Issues

**Do not open public issues for security vulnerabilities.**

Report security issues via:
- **Email**: security@valorcyber.com
- **GitHub**: Security tab → "Report a vulnerability"

See [SECURITY.md](SECURITY.md) for full disclosure policy.

## 💡 Feature Requests

Use the [Feature Request Template](/.github/ISSUE_TEMPLATE/feature_request.md):

1. Check existing issues first
2. Describe the use case clearly
3. Propose a solution if possible
4. Indicate if you're willing to implement

## 📁 Project Structure

```
ai-log-filter/
├── src/                    # Source code
│   ├── api/                # FastAPI endpoints
│   ├── models/             # ML models
│   ├── preprocessing/      # Log parsing, compliance
│   ├── routing/            # Log routing logic
│   ├── monitoring/         # Prometheus metrics
│   └── utils/              # Utilities, config
├── tests/                  # Test suite
├── scripts/                # Utility scripts
├── configs/                # Configuration files
├── deploy/                 # Kubernetes manifests
├── docs/                   # Documentation
└── .github/                # GitHub configs
```

## 📚 Resources

| Resource                        | Link                                              |
|---------------------------------|---------------------------------------------------|
| Architecture Documentation      | [docs/architecture/](docs/architecture/)          |
| API Reference                   | [docs/reference/API.md](docs/reference/API.md)    |
| Operations Runbook              | [docs/runbooks/](docs/runbooks/)                  |
| SOC Training Guide              | [docs/training/](docs/training/)                  |
| Branch Protection Rules         | [docs/guides/BRANCH_PROTECTION.md](docs/guides/BRANCH_PROTECTION.md) |

## 📜 License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for helping improve AI-Driven Log Filtering for SIEM! 🎉
