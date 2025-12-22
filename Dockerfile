# Soulcaster Backend - Production Dockerfile (builds from repo root)
# Uses uv for fast dependency installation and multi-stage build for smaller images

FROM python:3.11-slim as builder

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy dependency files from backend/ directory (layer caching optimization)
COPY backend/pyproject.toml ./
COPY backend/requirements.txt ./

# Install dependencies using uv (much faster than pip)
# Create a virtual environment and install dependencies
RUN uv venv /opt/venv && \
    . /opt/venv/bin/activate && \
    uv pip install -r requirements.txt

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

# Copy backend application code from backend/ directory
COPY --chown=soulcaster:soulcaster backend/ ./

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
