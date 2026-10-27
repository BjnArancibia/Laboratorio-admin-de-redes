"""Servicio catalog: lista productos desde PostgreSQL. NO modificar el código de la app.

Puerto interno: 8000
Variables de entorno: POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, DB_HOST (def. "db"),
                      CURRENCY (def. "USD"), TEAM_ID, TEAM_SECRET
"""
import hashlib
import hmac
import os

import psycopg2
from fastapi import FastAPI, HTTPException
from psycopg2.extras import RealDictCursor

app = FastAPI(title="catalog")


def db_conn():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "db"),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        connect_timeout=3,
    )


def team_token() -> str:
    secret = os.environ.get("TEAM_SECRET", "").encode()
    team = os.environ.get("TEAM_ID", "").encode()
    return hmac.new(secret, team, hashlib.sha256).hexdigest()[:16]


@app.get("/healthz")
def healthz():
    """Liveness: el proceso responde (no consulta la base de datos)."""
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    """Readiness: además hay conexión con la base de datos."""
    try:
        with db_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
        return {"status": "ready"}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc))


@app.get("/api/products")
def products():
    try:
        with db_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, name, price FROM products ORDER BY id")
            rows = cur.fetchall()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc))
    currency = os.environ.get("CURRENCY", "USD")
    return [
        {"id": r["id"], "name": r["name"], "price": float(r["price"]), "currency": currency}
        for r in rows
    ]


@app.get("/api/health")
def health():
    """Identifica el equipo que ejecuta este stack (lo usa el verificador)."""
    return {"team": os.environ.get("TEAM_ID", ""), "token": team_token()}
