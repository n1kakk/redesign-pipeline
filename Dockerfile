FROM python:3.11-slim

# ── dependencies ──────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# ── Python packages ───────────────────────────────────────────────
RUN pip install --no-cache-dir \
    openai \
    pillow \
    playwright

# ── Playwright (Chromium) ─────────────────────────────────────────
RUN npx playwright install chromium --with-deps 2>&1

# ── app ───────────────────────────────────────────────────────────
WORKDIR /app
COPY . .

# Playwright needs the Chromium binary location
ENV PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright

ENTRYPOINT ["python", "run.py"]
