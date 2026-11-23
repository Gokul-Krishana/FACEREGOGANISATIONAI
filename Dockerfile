# ─────────────────────────────────────────────────────────────────────
# Face Recognition AI — Multi-Stage Dockerfile (Linux Production)
# ─────────────────────────────────────────────────────────────────────
# Build:      docker build -t face-recognition-ai .
# Run API:    docker run -p 8000:8000 face-recognition-ai
# ─────────────────────────────────────────────────────────────────────

# ── Stage 1: Base Python image with runtime system dependencies ─────
FROM python:3.11-slim AS base

LABEL org.opencontainers.image.title="Face Recognition AI - College Deployment"
LABEL org.opencontainers.image.description="Multi-factor face recognition attendance system with AMFR anti-spoofing"
LABEL org.opencontainers.image.version="2.0.0"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies:
#   - OpenCV runtime libs (libgl1, libglib2.0)
#   - libmagic for upload security
#   - OpenMP (libgomp1) for FAISS and ONNX Runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libmagic1 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── Stage 2: Build dependencies ────────────────────────────────────
FROM base AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Use Linux requirements manifest
COPY requirements-linux.txt ./requirements.txt
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 3: Production image ──────────────────────────────────────
FROM base AS production

# Create non-root application user
RUN groupadd -r faceai && useradd -r -g faceai -d /app -s /sbin/nologin faceai

WORKDIR /app

# Copy installed Python packages to /usr/local (world-readable, standard PATH)
COPY --from=builder /install /usr/local

# Copy application code
COPY --chown=faceai:faceai . .

# Create runtime directories with non-root ownership
RUN mkdir -p /app/data /app/logs /app/embeddings /app/attendance /app/outputs /app/unknown_faces \
    && chown -R faceai:faceai /app

RUN chmod 1777 /tmp

USER faceai

# Built-in container healthcheck
HEALTHCHECK --interval=20s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

EXPOSE 8000

# Default command: run FastAPI production server
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]
