# ErgoVigilance YOLO Cloud Core
# RTSP ingestion + YOLOv8-pose + ByteTrack worker tracking
# Supports GPU inference via NVIDIA CUDA or CPU fallback

# ── GPU base image (NVIDIA runtime required on host) ──────────────
# When NVIDIA Container Toolkit is NOT available, Docker falls back to CPU.
# Build with: docker compose build (Compose handles the --gpus flag)
# Base images pinned by digest (P1 supply chain): tags kept for readability,
# digests make the build byte-reproducible. Re-pin deliberately via
#   docker buildx imagetools inspect <image>:<tag>
FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04@sha256:2fcc4280646484290cc50dce5e65f388dd04352b07cbe89a635703bd1f9aedb6 AS base-gpu

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
       python3.11 python3.11-venv python3-pip \
       libgl1 libglib2.0-0 libgomp1 ffmpeg \
    && ln -sf /usr/bin/python3.11 /usr/bin/python \
    && rm -rf /var/lib/apt/lists/*

# ── CPU-only fallback ─────────────────────────────────────────────
FROM python:3.11-slim@sha256:e41613d42d4891e4930f79523f93f81bbc7632584ec65e36ab055f41a800b41e AS base-cpu

RUN apt-get update && apt-get install -y --no-install-recommends \
       libgl1 libglib2.0-0 libgomp1 ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# ── Default to CPU build; Compose overrides with base-gpu ─────────
FROM base-cpu AS build

WORKDIR /app

# Install Python dependencies
COPY yolo_cloud/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --retries 3 --timeout 120 \
    -r /tmp/requirements.txt && rm /tmp/requirements.txt

# Download YOLO model at build time (avoids cold-start on first run)
RUN python -c "from ultralytics import YOLO; YOLO('yolov8s-pose.pt')" || true

# ── Non-root user ─────────────────────────────────────────────────
RUN groupadd -r cloud && useradd -r -g cloud -d /app -s /sbin/nologin cloud

# Application code
COPY yolo_cloud/ ./yolo_cloud/
COPY backend/ ./backend/
COPY models/ ./models/

# Data directories
RUN mkdir -p /data/sessions /data/recordings /data/reports \
    && chown -R cloud:cloud /app /data

USER cloud

EXPOSE 8100

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8100/healthz', timeout=3)"

CMD ["uvicorn", "yolo_cloud.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8100"]
