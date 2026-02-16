# =============================================================================
# AI Log Filter - Dockerfile
# =============================================================================

FROM python:3.14-slim AS base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install only runtime system dependencies in base
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# =============================================================================
# Builder stage - install build tools and Python deps
# =============================================================================
FROM base AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml ./
RUN pip install --upgrade pip && \
    pip install .

# =============================================================================
# Production stage - minimal runtime image
# =============================================================================
FROM base AS production

# Create non-root user
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home appuser

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY src/ ./src/
COPY configs/ ./configs/
COPY scripts/ ./scripts/

# Create directories
RUN mkdir -p /app/models /app/logs /app/data && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose ports
EXPOSE 8000 9090

# Health check - use the lightweight liveness endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1

# Default command
CMD ["python", "-m", "src.main"]
