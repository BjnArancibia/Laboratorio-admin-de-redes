# syntax=docker/dockerfile:1

FROM python:3.12-alpine AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install -r requirements.txt

FROM python:3.12-alpine

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apk add --no-cache libpq \
    && addgroup -S -g 10001 app \
    && adduser -S -D -H -u 10001 -G app -s /sbin/nologin app

COPY --from=builder --chown=10001:10001 /opt/venv /opt/venv

WORKDIR /app
COPY --chown=10001:10001 worker.py .

USER 10001:10001

# no tiene HTTP, se revisa que /tmp/healthy se haya actualizado hace menos de 30 s
HEALTHCHECK --interval=5s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import os, sys, time; sys.exit(0 if time.time() - os.path.getmtime('/tmp/healthy') < 30 else 1)"]

CMD ["python", "worker.py"]
