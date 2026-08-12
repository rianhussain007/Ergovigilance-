FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for playwright and opencv
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY backend_api/requirements.txt .
# Local dev only: this machine's proxy presents a self-signed certificate, so
# pip's cert verification fails on PyPI downloads (same category as the
# playwright NODE_TLS_REJECT_UNAUTHORIZED below). Bypass verification for the
# PyPI hosts only — production should drop these flags and use PIP_CERT.
RUN pip install --no-cache-dir \
    --trusted-host pypi.org \
    --trusted-host files.pythonhosted.org \
    -r requirements.txt

# Install playwright chromium (temporarily skip cert verification for local dev build only)
RUN NODE_TLS_REJECT_UNAUTHORIZED=0 playwright install chromium --with-deps

# Copy application code
COPY backend_api/app/ ./app/
COPY backend/ ./backend/
COPY models/ ./models/

# Expose API port
EXPOSE 8000

# Run uvicorn (app will initialize db on startup)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
