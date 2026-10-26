"""Servicio worker: consume pedidos de Redis y los marca como 'processed' en PostgreSQL.
NO modificar el código de la app.

Cada ciclo (máx. ~5 s) actualiza la fecha de modificación del archivo HEARTBEAT_FILE
(por defecto /tmp/healthy). Puedes usarlo para definir el healthcheck del contenedor.

Variables: POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, DB_HOST (def. "db"), REDIS_HOST (def. "cache")
"""
import os
import pathlib
import sys
import time

import psycopg2
import redis

HEARTBEAT = pathlib.Path(os.environ.get("HEARTBEAT_FILE", "/tmp/healthy"))


def log(msg: str) -> None:
    print(msg, flush=True)


def beat() -> None:
    HEARTBEAT.touch()


def connect_db():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "db"),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        connect_timeout=3,
    )


def connect_redis():
    return redis.Redis(host=os.environ.get("REDIS_HOST", "cache"), port=6379, socket_timeout=10)


def process(db, order_id: int) -> None:
    time.sleep(0.5)  # simula trabajo
    with db.cursor() as cur:
        cur.execute(
            "UPDATE orders SET status = 'processed', processed_at = now() WHERE id = %s",
            (order_id,),
        )
    db.commit()
    log(f"pedido {order_id} procesado")


def main() -> None:
    db = None
    r = None
    beat()
    while True:
        try:
            if db is None or db.closed:
                db = connect_db()
            if r is None:
                r = connect_redis()
            item = r.brpop("orders", timeout=5)
            beat()
            if item:
                process(db, int(item[1]))
        except (redis.RedisError, psycopg2.Error, OSError) as exc:
            log(f"error: {exc}; reintentando en 2 s")
            r = None
            if db is not None:
                try:
                    db.close()
                except Exception:  # noqa: BLE001
                    pass
            db = None
            time.sleep(2)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
