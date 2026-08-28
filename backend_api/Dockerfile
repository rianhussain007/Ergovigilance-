FROM python:3.12-slim

WORKDIR /app

# ── System dependencies for OpenCV ─────────────────────────────────
# Minimal set: just what MediaPipe + OpenCV need. Skip Playwright
# (only needed for PDF export — install separately if required).
RUN apt-get update && apt-get install -y --no-install-recommends \
       libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# ── Python dependencies ────────────────────────────────────────────
COPY backend_api/requirements.txt .
RUN pip install --no-cache-dir --retries 3 --timeout 120 \
    -r requirements.txt

# ── Application code ───────────────────────────────────────────────
COPY backend_api/app/ ./app/
COPY backend/ ./backend/
COPY models/ ./models/

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
