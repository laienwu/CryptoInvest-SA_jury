# Portfolio Optimization - Data Engineer Project
# Multi-stage build for smaller image

FROM python:3.12-slim AS builder

# Install uv
RUN pip install uv

WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Production image
FROM python:3.12-slim

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy source code
COPY src/ ./src/
COPY config.toml ./

# Create data directories
RUN mkdir -p data/raw/klines data/processed data/output

# Set environment
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"

# Expose API port
EXPOSE 8000

# Default: run API
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
