FROM python:3.12-slim

WORKDIR /app

# ── System dependencies for Playwright + OpenCV ─────────────────────
# Corporate proxy intercepts HTTPS and corrupts GPG signatures.
# Disable signature verification for the build stage only.
RUN echo 'APT::Get::AllowUnauthenticated "true";' >> /etc/apt/apt.conf.d/99insecure \
    && echo 'Acquire::AllowInsecureRepositories "true";' >> /etc/apt/apt.conf.d/99insecure \
    && echo 'Acquire::AllowDowngradeToInsecureRepositories "true";' >> /etc/apt/apt.conf.d/99insecure \
    && apt-get update --allow-releaseinfo-change \
    && apt-get install -y --allow-unauthenticated --no-install-recommends \
       libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
       libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
       libxfixes3 libxrandr2 libgbm1 libasound2 \
       libgl1 libglib2.0-0 \ 
       curl ca-certificates fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# ── Python dependencies ────────────────────────────────────────────
COPY backend_api/requirements.txt .
RUN pip install --no-cache-dir --retries 5 --timeout 120 \
    --trusted-host pypi.org --trusted-host files.pythonhosted.org \
    --trusted-host pypi.python.org --trusted-host *.pypi.org \
    --trusted-host *.pythonhosted.org \
    -r requirements.txt

# ── Playwright Chromium ────────────────────────────────────────────
# Skip --with-deps since apt deps are already installed above.
ENV NODE_TLS_REJECT_UNAUTHORIZED=0
RUN python -m playwright install chromium

# ── Application code ───────────────────────────────────────────────
COPY backend_api/app/ ./app/
COPY backend/ ./backend/
COPY models/ ./models/

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
