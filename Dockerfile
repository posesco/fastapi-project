# ─── Build stage 
FROM python:3.14-slim AS builder

WORKDIR /app

# VIRTUAL_ENV is the standard env variable for virtual environments, and PATH is updated to prioritize it.
RUN python -m venv /app/.venv
ENV VIRTUAL_ENV="/app/.venv" \
    PATH="/app/.venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ─── Dev stage 
FROM python:3.14-slim AS dev

# Prevents .pyc file creation and disables buffering for real-time logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV="/app/.venv" \
    PATH="/app/.venv/bin:$PATH" \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app --no-create-home app

COPY --from=builder --chown=app:app /app/.venv /app/.venv

USER app

EXPOSE 8000

CMD ["fastapi", "dev", "src/main.py", "--host", "0.0.0.0", "--port", "8000"]

# ─── Runtime stage ──────────────────────────────────────────────────────────
FROM python:3.14-slim AS runtime

ARG BUILD_DATE
ARG GIT_COMMIT
ARG VERSION

LABEL org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${GIT_COMMIT}" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.title="fastapi-app" \
      org.opencontainers.image.base.name="python:3.14-slim"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV="/app/.venv" \
    PATH="/app/.venv/bin:$PATH" \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Prevent hash flooding DoS attacks in production
    PYTHONHASHSEED=random

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app --no-create-home app

COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --chown=app:app ./src ./src

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c \
    "import urllib.request; urllib.request.urlopen('http://localhost:8000/health-check/')"

CMD ["bash", "-c", "alembic upgrade head && fastapi run src/main.py --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]