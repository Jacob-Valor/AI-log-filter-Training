# =============================================================================
# AI Log Filter - Makefile
# =============================================================================

.PHONY: help install install-dev test lint format clean docker-build docker-up docker-down train evaluate

# Default target
help:
	@echo "AI Log Filter - Available Commands"
	@echo "=================================="
	@echo ""
	@echo "Setup:"
	@echo "  make install        Install production dependencies"
	@echo "  make install-dev    Install development dependencies"
	@echo "  make setup          Full development setup"
	@echo ""
	@echo "Development:"
	@echo "  make test           Run tests with coverage"
	@echo "  make test-fast      Run tests without coverage"
	@echo "  make lint           Run linting checks (Ruff)"
	@echo "  make format         Format code (Ruff)"
	@echo "  make check          Run all checks (lint + test)"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build   Build Docker images"
	@echo "  make docker-up      Start all services"
	@echo "  make docker-down    Stop all services"
	@echo "  make docker-logs    View service logs"
	@echo ""
	@echo "ML Pipeline:"
	@echo "  make train          Train the model"
	@echo "  make evaluate       Evaluate model performance"
	@echo "  make export         Export model for production"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean          Clean build artifacts"
	@echo "  make clean-all      Clean everything including models"

# =============================================================================
# Setup
# =============================================================================

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"
	pip install pre-commit
	pre-commit install

setup: install-dev
	@echo "Creating necessary directories..."
	mkdir -p data/{raw,processed,labeled,samples}
	mkdir -p models
	mkdir -p logs
	@echo "Setup complete!"

# =============================================================================
# Development
# =============================================================================

test:
	pytest tests/ -v --cov=src --cov-report=term-missing --cov-report=html

test-fast:
	pytest tests/ -v -x --no-cov

lint:
	ruff check src/ scripts/ tests/

format:
	ruff format src/ scripts/ tests/
	ruff check --fix src/ scripts/ tests/

check: lint test

# =============================================================================
# Docker
# =============================================================================

docker-build:
	docker-compose build

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-restart: docker-down docker-up

# =============================================================================
# ML Pipeline
# =============================================================================

train:
	python scripts/train.py --config configs/model_config.yaml

train-tfidf:
	python scripts/train.py --config configs/model_config.yaml --model-type tfidf

train-bert:
	python scripts/train.py --config configs/model_config.yaml --model-type bert

train-ensemble:
	python scripts/train.py --config configs/model_config.yaml --model-type ensemble

evaluate:
	python scripts/evaluate.py --model models/latest --test-data data/labeled/test.csv

export:
	python scripts/export_model.py --model models/latest --output models/production

# =============================================================================
# Data Pipeline
# =============================================================================

prepare-data:
	python scripts/prepare_data.py --input data/raw --output data/processed

label-data:
	python scripts/label_data.py --input data/processed --output data/labeled

# =============================================================================
# Utilities
# =============================================================================

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache/
	rm -rf .ruff_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

clean-all: clean
	rm -rf models/*
	rm -rf data/processed/*
	rm -rf logs/*

# =============================================================================
# Run Services
# =============================================================================

run-api:
	uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --reload

run-consumer:
	python -m src.main --mode consumer

run-processor:
	python -m src.main --mode processor
