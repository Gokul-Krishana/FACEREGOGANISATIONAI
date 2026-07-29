# ─────────────────────────────────────────────────────────────────────
# Face Recognition AI — Multi-Stage Dockerfile
# ─────────────────────────────────────────────────────────────────────
# Build:      docker build -t face-recognition-ai .
# Run API:    docker run --gpus all -p 8000:8000 face-recognition-ai
# ─────────────────────────────────────────────────────────────────────

# ── Stage 1: Base Python image with system deps ────────────────────
FROM python:3.11-slim AS base

LABEL org.opencontainers.image.title="Face Recognition AI - College Deployment"
LABEL org.opencontainers.image.description="Multi-factor face recognition attendance system with AMFR anti-spoofing"
LABEL org.opencontainers.image.version="2.0.0"

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies:
#   - OpenCV runtime libs (libgl1, libglib2.0)
#   - libmagic for upload security
#   - libsndfile for torch audio (optional)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libmagic1 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# ── Stage 2: Build dependencies (compile heavy packages) ───────────
FROM base AS builder

WORKDIR /build

# Install Python build deps
COPY requirements.txt .
RUN pip install --user --no-warn-script-location \
    --no-cache-dir \
    -r requirements.txt

# ── Stage 3: Production image ──────────────────────────────────────
FROM base AS production

# Create non-root user
RUN groupadd -r faceai && useradd -r -g faceai -d /app -s /sbin/nologin faceai

WORKDIR /app

# Copy installed Python packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY --chown=faceai:faceai . .

# Create required directories with proper permissions
RUN mkdir -p /app/data /app/logs /app/embeddings /app/outputs /app/unknown_faces \
    && chown -R faceai:faceai /app/data /app/logs /app/embeddings /app/outputs /app/unknown_faces

# Ensure /tmp is writable by the non-root user (needed for various libraries)
RUN chmod 1777 /tmp

# Switch to non-root user
USER faceai

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Expose API port
EXPOSE 8000

# Security: run with read-only root filesystem (tmpfs for writable paths)
# When using --read-only, mount these as tmpfs:
#   /app/data, /app/logs, /app/embeddings, /app/outputs, /app/unknown_faces, /app/uploads, /tmp
# See docker-compose.yml for the full --read-only configuration

# Default command: run the FastAPI server
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]
