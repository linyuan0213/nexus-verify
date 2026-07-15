# Nexus Verify (OCR) Dockerfile
# Multi-stage build using uv; runs directly from source, no wheel build required.

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        libffi-dev \
        libssl-dev \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender-dev \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy project metadata and lockfile
COPY pyproject.toml uv.lock ./

# Sync production dependencies only (no package build needed)
RUN uv sync --frozen --no-cache --no-dev

# ==================== Runtime ====================
FROM python:3.12-slim-bookworm

WORKDIR /app

# Install runtime dependencies for OpenCV / ONNX runtime
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgl1-mesa-glx \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender1 \
        libgomp1 \
        curl \
        tzdata \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r nexus && useradd -r -g nexus -d /app -s /bin/bash nexus

# Copy uv binary, application source, and virtual environment
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
COPY --chown=nexus:nexus . .
COPY --from=builder --chown=nexus:nexus /app/.venv ./.venv

USER nexus

ENV TZ=Asia/Shanghai \
    PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    UV_NO_SYNC=1

EXPOSE 9300

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -fs http://localhost:9300/health || exit 1

CMD ["uv", "run", "python", "-m", "nexus_verify.main"]
