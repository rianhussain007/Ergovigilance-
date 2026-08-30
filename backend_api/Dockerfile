FROM python:3.12-slim

# ── System dependencies for OpenCV ─────────────────────────────────
# Minimal set: just what MediaPipe + OpenCV need. Skip Playwright
# (only needed for PDF export — install separately if required).
RUN apt-get update && apt-get install -y --no-install-recommends \
       libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# ── Python dependencies ────────────────────────────────────────────
COPY backend_api/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --retries 3 --timeout 120 \
    -r /tmp/requirements.txt && rm /tmp/requirements.txt

# ── Non-root user ──────────────────────────────────────────────────
RUN groupadd -r ergovigilance && useradd -r -g ergovigilance -d /app -s /sbin/nologin ergovigilance

# ── Application code ───────────────────────────────────────────────
WORKDIR /app
COPY backend_api/app/ ./app/
COPY backend/ ./backend/
COPY models/ ./models/

# ── Data directories (writable by app user) ───────────────────────
RUN mkdir -p /data/sessions /data/recordings /data/reports \
    && chown -R ergovigilance:ergovigilance /app /data

USER ergovigilance

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz', timeout=3)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
