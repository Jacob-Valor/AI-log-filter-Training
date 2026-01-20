# =============================================================================
# AI Log Filter - Dockerfile
# =============================================================================

FROM python:3.14-slim as base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# =============================================================================
# Builder stage
# =============================================================================
FROM base as builder

# Install Python dependencies
COPY pyproject.toml ./
RUN pip install --upgrade pip && \
    pip wheel --no-deps --wheel-dir /app/wheels -e .

# =============================================================================
# Production stage
# =============================================================================
FROM base as production

# Create non-root user
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home appuser

# Copy wheels and install
COPY --from=builder /app/wheels /wheels
RUN pip install --no-deps /wheels/* && \
    rm -rf /wheels

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

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["python", "-m", "src.main"]
