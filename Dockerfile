# Portfolio Optimization - Data Engineer Project

FROM python:3.13-slim

# Install uv
RUN pip install "uv>=0.9,<1"

WORKDIR /app

# Copy dependency files and install
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

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
CMD ["python", "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
