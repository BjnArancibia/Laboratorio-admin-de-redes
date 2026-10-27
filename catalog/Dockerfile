# syntax=docker/dockerfile:1

# etapa de build: dependencias en un venv
FROM python:3.12-alpine AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# requirements antes que el código para aprovechar la caché
COPY requirements.txt .
RUN pip install -r requirements.txt

# imagen final
FROM python:3.12-alpine

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apk add --no-cache libpq \
    && addgroup -S -g 10001 app \
    && adduser -S -D -H -u 10001 -G app -s /sbin/nologin app

COPY --from=builder --chown=10001:10001 /opt/venv /opt/venv

WORKDIR /app
COPY --chown=10001:10001 app ./app

USER 10001:10001

EXPOSE 8000

# readyz también revisa la conexión a la base
HEALTHCHECK --interval=5s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/readyz', timeout=2)"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
