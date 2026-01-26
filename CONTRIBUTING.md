# Contributing to AI-Driven Log Filtering for SIEM

Thank you for your interest in contributing! This document provides guidelines for contributing to this project.

## 🚀 Quick Start

1. **Fork** the repository
2. **Clone** your fork: `git clone https://github.com/yourusername/ai-log-filter.git`
3. **Create a branch**: `git checkout -b feature/your-feature-name`
4. **Install dependencies**: `pip install -e ".[dev]"`
5. **Make your changes**
6. **Run tests**: `pytest`
7. **Submit a Pull Request**

## 📋 Development Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install with dev dependencies
pip install -e ".[dev]"

# Run linter
ruff check src/ tests/

# Run tests
pytest tests/ -v
```

## 🔧 Code Style

- **Formatter**: Ruff (configured in `pyproject.toml`)
- **Type hints**: Required for public functions
- **Docstrings**: Google-style docstrings for modules, classes, and functions

```bash
# Format code
ruff format src/ tests/

# Check linting
ruff check src/ tests/ --fix
```

## 📝 Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): description

[optional body]

[optional footer]
```

**Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

**Examples**:

```
feat(models): add new anomaly detection algorithm
fix(kafka): resolve consumer lag issue
docs(readme): update installation instructions
```

## 🧪 Testing Requirements

- All new features must have tests
- Maintain or improve code coverage
- All tests must pass before merging

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

## 📤 Pull Request Process

1. **Update documentation** for any new features
2. **Add tests** for new functionality
3. **Ensure all checks pass** (linting, tests)
4. **Update CHANGELOG.md** if applicable
5. **Request review** from maintainers

## 🐛 Reporting Issues

When reporting bugs, include:

- Python version (`python --version`)
- Operating system
- Steps to reproduce
- Expected vs actual behavior
- Relevant logs or error messages

## 💡 Feature Requests

For new features:

- Check existing issues first
- Describe the use case
- Propose a solution if possible

## 📜 License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for helping improve AI-Driven Log Filtering for SIEM! 🎉
