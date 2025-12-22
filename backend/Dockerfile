# Soulcaster Backend - Production Dockerfile
# Uses uv for fast dependency installation and multi-stage build for smaller images

FROM python:3.11-slim as builder

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy dependency files first (layer caching optimization)
COPY pyproject.toml ./
COPY uv.lock ./

# Install dependencies using uv sync (reads from pyproject.toml)
# Creates a virtual environment and installs all dependencies
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
RUN uv sync --frozen --no-dev

# Production stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd -m -u 1000 soulcaster && \
    mkdir -p /app && \
    chown -R soulcaster:soulcaster /app

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder --chown=soulcaster:soulcaster /opt/venv /opt/venv

# Copy application code
COPY --chown=soulcaster:soulcaster . .

# Switch to non-root user
USER soulcaster

# Add venv to PATH
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Expose port (most hosting providers use 8000 or $PORT)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health', timeout=5)"

# Start uvicorn
# Note: Railway/Render often set $PORT env var, so we support both
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
