# HYDRA Arm 3 — Regulatory Intelligence SaaS
# Multi-stage Docker build for production deployment

# ─────────────────────────────────────────────────────────────
# Stage 1: Builder — install dependencies
# ─────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

# System dependencies for cryptographic libraries and lxml
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libssl-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install Python dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt


# ─────────────────────────────────────────────────────────────
# Stage 2: Runtime — minimal production image
# ─────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Non-root user for security
RUN groupadd -r hydra && useradd -r -g hydra -d /app -s /sbin/nologin hydra

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy application code
COPY config/ ./config/
COPY src/ ./src/
COPY .env.example .env.example

# Create persistent data directory
RUN mkdir -p /app/data && chown hydra:hydra /app/data

# Ensure Python can find the app root
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HYDRA_STATE_DIR=/app/data

# Port 8402 — HTTP 402 reference
EXPOSE 8402

# Switch to non-root user
USER hydra

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8402/health')" || exit 1

# Start server with 4 workers for production throughput
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8402", "--workers", "4", "--timeout-keep-alive", "30", "--log-level", "info"]
