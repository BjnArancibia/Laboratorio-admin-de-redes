#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify.py — Verificador del laboratorio "Operación Despliegue".

Mide lo mismo que usará el docente (50 puntos automáticos: 30 de funcionamiento y 20 de calidad).
Los incidentes, el registro de decisiones, la defensa y la coevaluación se evalúan aparte.

Uso (desde la raíz del repositorio del equipo):
    python3 tools/verify.py                 # construye, levanta y mide todo
    python3 tools/verify.py --static        # solo revisiones que no necesitan Docker
    python3 tools/verify.py --down          # apaga el stack al terminar
    python3 tools/verify.py --json out.json # guarda el informe en JSON

Requiere: Python 3.9+, Docker Engine con Compose v2 (docker compose).
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

APP_SERVICES = ["frontend", "catalog", "orders", "worker"]
SIZE_LIMIT_MB = {"frontend": 100, "catalog": 250, "orders": 250, "worker": 250}
ROOT_USERS = {"", "0", "root"}

G_FUNC = "Funcionamiento (30)"
G_QUAL = "Calidad (20)"


# --------------------------------------------------------------------------- utilidades
def load_env(path: Path) -> dict:
    env = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def sh(cmd, cwd=None, timeout=300):
    """Ejecuta un comando. Devuelve (código, salida combinada)."""
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, errors="replace")
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, f"tiempo agotado ({timeout}s)"
    except FileNotFoundError:
        return 127, f"no se encontró el comando: {cmd[0]}"


_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # nunca usar proxy para localhost


def http(method, url, body=None, timeout=6):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with _OPENER.open(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return 0, str(e)


def wait_http(url, seconds=30):
    end = time.time() + seconds
    status, body = 0, ""
    while time.time() < end:
        status, body = http("GET", url)
        if status == 200:
            return status, body
        time.sleep(1)
    return status, body


def expected_token(team_id: str, secret: str) -> str:
    return hmac.new(secret.encode(), team_id.encode(), hashlib.sha256).hexdigest()[:16]


def team_secret_from_master(master: str, team_id: str) -> str:
    return hmac.new(master.encode(), team_id.encode(), hashlib.sha256).hexdigest()


class Report:
    def __init__(self, team):
        self.team = team
        self.checks = []
        self.flags = {}

    def add(self, cid, group, label, max_pts, got, detail=""):
        got = max(0.0, min(float(max_pts), float(got)))
        self.checks.append({
            "id": cid, "group": group, "label": label, "max": max_pts,
            "points": round(got, 2), "ok": got >= max_pts, "detail": detail,
        })

    def total(self):
        return round(sum(c["points"] for c in self.checks), 2)

    def total_max(self):
        return round(sum(c["max"] for c in self.checks), 2)

    def to_dict(self):
        return {"team": self.team, "total": self.total(), "max": self.total_max(),
                "flags": self.flags, "checks": self.checks}

    def print(self):
        print(f"\n=== Informe de {self.team} ===")
        group = None
        for c in self.checks:
            if c["group"] != group:
                group = c["group"]
                print(f"\n{group}")
            mark = "OK " if c["ok"] else ("~  " if c["points"] > 0 else "NO ")
            print(f"  [{mark}] {c['points']:>5g}/{c['max']:<3g} {c['label']}" + (f"  -> {c['detail']}" if c["detail"] and not c["ok"] else ""))
        print(f"\nTOTAL AUTOMÁTICO: {self.total():g} / {self.total_max():g}")
        for k, v in self.flags.items():
            if v:
                print(f"  AVISO {k}: {v}")


class Lab:
    """Un stack del laboratorio (carpeta del equipo + nombre de proyecto de compose)."""

    def __init__(self, directory, project=None):
        self.dir = Path(directory).resolve()
        self.env = load_env(self.dir / ".env")
        self.team = self.env.get("TEAM_ID", self.dir.name)
        self.project = project or self.team
        self.port = int(self.env.get("FRONTEND_PORT", "8080"))

    def compose(self, *args, timeout=300):
        return sh(["docker", "compose", "-p", self.project, *args], cwd=self.dir, timeout=timeout)

    def up(self, build=True):
        args = ["up", "-d"] + (["--build"] if build else []) + ["--wait", "--wait-timeout", "150"]
        return self.compose(*args, timeout=1500)

    def down(self):
        return self.compose("down", "--remove-orphans", timeout=240)

    def cid(self, service):
        rc, out = self.compose("ps", "-a", "-q", service)
        ids = out.split() if rc == 0 else []
        return ids[0] if ids else None

    def inspect(self, ref):
        rc, out = sh(["docker", "inspect", ref])
        try:
            return json.loads(out)[0] if rc == 0 else None
        except (ValueError, IndexError):
            return None

    def url(self, path, port=None):
        return f"http://127.0.0.1:{port or self.port}{path}"


def order_flow(lab: Lab, port=None, timeout=25):
    """Crea un pedido y espera a que el worker lo marque como 'processed'. -> (ok, detalle, id)"""
    status, body = http("POST", lab.url("/api/orders", port), {"product_id": 1, "qty": 2})
    if status not in (200, 201):
        return False, f"POST /api/orders respondió {status}: {body[:120]}", None
    try:
        oid = json.loads(body)["id"]
    except (ValueError, KeyError, TypeError):
        return False, f"respuesta inesperada de POST /api/orders: {body[:120]}", None
    end = time.time() + timeout
    last = ""
    while time.time() < end:
        status, body = http("GET", lab.url(f"/api/orders/{oid}", port))
        last = body[:100]
        if status == 200:
            try:
                if json.loads(body).get("status") == "processed":
                    return True, "", oid
            except ValueError:
                pass
        time.sleep(1)
    return False, f"el pedido {oid} no llegó a 'processed' en {timeout}s (último estado: {last})", oid


# --------------------------------------------------------------------------- revisiones estáticas
def from_lines(dockerfile: Path):
    if not dockerfile.exists():
        return []
    return re.findall(r"^\s*FROM\s", dockerfile.read_text(encoding="utf-8", errors="replace"),
                      flags=re.IGNORECASE | re.MULTILINE)


def check_static(lab: Lab, rep: Report):
    # multi-stage en catalog y orders (0.5 c/u)
    got, notes = 0.0, []
    for svc in ("catalog", "orders"):
        n = len(from_lines(lab.dir / svc / "Dockerfile"))
        if n >= 2:
            got += 0.5
        else:
            notes.append(f"{svc}/Dockerfile tiene {n} FROM")
    rep.add("multistage", G_QUAL, "Multi-stage build en catalog y orders", 1, got, "; ".join(notes))

    # .dockerignore en los 4 servicios (0.25 c/u)
    got, notes = 0.0, []
    for svc in APP_SERVICES:
        f = lab.dir / svc / ".dockerignore"
        if f.exists() and f.read_text(encoding="utf-8", errors="replace").strip():
            got += 0.25
        else:
            notes.append(f"falta {svc}/.dockerignore")
    rep.add("dockerignore", G_QUAL, ".dockerignore en los 4 servicios", 1, got, "; ".join(notes))


def app_code_modified(lab: Lab, hashes_file=None):
    f = Path(hashes_file) if hashes_file else lab.dir / ".lab" / "hashes.json"
    if not f.exists():
        return []
    try:
        expected = json.loads(f.read_text(encoding="utf-8"))
    except ValueError:
        return []
    changed = []
    for rel, digest in expected.items():
        p = lab.dir / rel
        if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest() != digest:
            changed.append(rel)
    return changed


# --------------------------------------------------------------------------- revisiones con Docker
def check_functional(lab: Lab, rep: Report, up_ok: bool, up_detail: str, master: str | None):
    if not up_ok:
        why = "el stack no levantó: " + up_detail.strip().splitlines()[-1][:150] if up_detail.strip() else "el stack no levantó"
        rep.add("up", G_FUNC, "docker compose up levanta todo", 5, 0, why)
        for cid, label, mx in (("frontend", "Frontend responde con la página del equipo", 5),
                               ("catalog", "Catálogo lee productos de la base de datos", 5),
                               ("orders_flow", "Pedido recorre orders → Redis → worker → base de datos", 10)):
            rep.add(cid, G_FUNC, label, mx, 0, "el stack no está arriba")
        return None
    rep.add("up", G_FUNC, "docker compose up levanta todo", 5, 5)

    status, body = wait_http(lab.url("/"), 30)
    ok = status == 200 and lab.team in body
    rep.add("frontend", G_FUNC, "Frontend responde con la página del equipo", 5, 5 if ok else 0,
            "" if ok else f"GET / → {status}" + ("" if status != 200 else " (no aparece el identificador del equipo)"))

    status, body = wait_http(lab.url("/api/products"), 30)
    ok, detail = False, f"GET /api/products → {status}"
    if status == 200:
        try:
            items = json.loads(body)
            ok = isinstance(items, list) and len(items) >= 3 and all({"id", "name", "price"} <= set(i) for i in items)
            detail = "" if ok else "la respuesta no es la lista de productos esperada"
        except ValueError:
            detail = "la respuesta no es JSON"
    rep.add("catalog", G_FUNC, "Catálogo lee productos de la base de datos", 5, 5 if ok else 0, detail)

    # identidad del stack (integridad; no suma puntos)
    status, body = http("GET", lab.url("/api/health"))
    secret = team_secret_from_master(master, lab.team) if master else lab.env.get("TEAM_SECRET", "")
    try:
        data = json.loads(body)
        token_ok = data.get("team") == lab.team and data.get("token") == expected_token(lab.team, secret)
    except ValueError:
        token_ok = False
    rep.flags["identidad_del_stack"] = "" if token_ok else "/api/health no coincide con este equipo (¿se copió código o .env de otro equipo?)"

    ok, detail, oid = order_flow(lab)
    rep.add("orders_flow", G_FUNC, "Pedido recorre orders → Redis → worker → base de datos", 10, 10 if ok else 0, detail)
    return oid


def check_images(lab: Lab, rep: Report):
    pw = lab.env.get("POSTGRES_PASSWORD", "")
    secret = lab.env.get("TEAM_SECRET", "")
    sizes, users, health, secrets = {}, {}, {}, {}
    for svc in APP_SERVICES:
        cid = lab.cid(svc)
        c = lab.inspect(cid) if cid else None
        if not c:
            for d in (sizes, users, health, secrets):
                d[svc] = (0, "sin contenedor")
            continue
        cfg = c.get("Config", {})
        image = lab.inspect(c.get("Image", "")) or {}

        size_mb = (image.get("Size") or 0) / 1_000_000
        limit = SIZE_LIMIT_MB[svc]
        sizes[svc] = (1 if 0 < size_mb <= limit else 0, f"{size_mb:.0f} MB (límite {limit} MB)")

        user = (cfg.get("User") or "").split(":")[0]
        users[svc] = (0 if user in ROOT_USERS else 1, "corre como root" if user in ROOT_USERS else "")

        hc = cfg.get("Healthcheck") or {}
        test = hc.get("Test") or []
        health[svc] = (1 if test and test[0] != "NONE" else 0, "sin HEALTHCHECK")

        rc, hist = sh(["docker", "history", "--no-trunc", "--format", "{{.CreatedBy}}", c.get("Image", "")])
        blob = hist + json.dumps(image.get("Config", {}))
        leaked = [name for name, val in (("POSTGRES_PASSWORD", pw), ("TEAM_SECRET", secret)) if val and val in blob]
        secrets[svc] = (0 if leaked else 1, "secreto visible en la imagen: " + ", ".join(leaked) if leaked else "")

    for cid, label, data in (("size", "Tamaño de imagen dentro del límite", sizes),
                             ("nonroot", "Contenedor corre como usuario no root", users),
                             ("healthcheck", "HEALTHCHECK definido", health),
                             ("secrets", "Sin secretos en capas ni en ENV de la imagen", secrets)):
        got = sum(v[0] for v in data.values())
        notes = [f"{svc}: {v[1]}" for svc, v in data.items() if v[1] and (cid == "size" or not v[0])]
        rep.add(cid, G_QUAL, label + " (1 pt por servicio)", 4, got, "; ".join(notes))


def parse_cache_log(log: str):
    steps, cached = {}, set()
    step_re = re.compile(r"^#(\d+) \[(.+?)\] (.*)$")
    cached_re = re.compile(r"^#(\d+) CACHED")
    install_re = re.compile(r"\b(pip3?\s+(install|wheel|download)|npm\s+(ci|install)|yarn\s+install|pnpm\s+install|uv\s+(pip|sync))\b")
    for line in log.splitlines():
        m = step_re.match(line)
        if m:
            steps[m.group(1)] = m.group(3)
            continue
        m = cached_re.match(line)
        if m:
            cached.add(m.group(1))
    installs = [n for n, text in steps.items() if install_re.search(text)]
    if not installs:
        return False, "no se encontró el paso que instala dependencias"
    not_cached = [steps[n][:50] for n in installs if n not in cached]
    if not_cached:
        return False, "se reinstalan dependencias al cambiar el código (" + not_cached[0] + "…)"
    return True, ""


def check_cache(lab: Lab, rep: Report):
    tmp = Path(tempfile.mkdtemp(prefix="lab-cache-"))
    got, notes = 0.0, []
    try:
        dst = tmp / "p"
        shutil.copytree(lab.dir, dst, ignore=shutil.ignore_patterns(".git", "node_modules", "__pycache__"))
        edits = {"catalog": (dst / "catalog" / "app" / "main.py", "\n# cambio trivial\n"),
                 "orders": (dst / "orders" / "server.js", "\n// cambio trivial\n")}
        for f, text in edits.values():
            if f.exists():
                with open(f, "a", encoding="utf-8") as fh:
                    fh.write(text)
        project = lab.project + "-cache"
        for svc in ("catalog", "orders"):
            rc, out = sh(["docker", "compose", "-p", project, "--progress", "plain", "build", svc], cwd=dst, timeout=900)
            if rc != 0:
                notes.append(f"{svc}: no construyó en la copia de prueba")
                continue
            ok, why = parse_cache_log(out)
            if ok:
                got += 0.5
            else:
                notes.append(f"{svc}: {why}")
        sh(["docker", "compose", "-p", project, "down", "--rmi", "local"], cwd=dst, timeout=120)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    rep.add("cache_layers", G_QUAL, "Caché de capas: cambiar código no reinstala dependencias", 1, got, "; ".join(notes))


def check_compose_structure(lab: Lab, rep: Report):
    got, notes = 0.0, []
    # redes: frontend y db no comparten ninguna red
    nets = {}
    for svc in ("frontend", "db"):
        cid = lab.cid(svc)
        c = lab.inspect(cid) if cid else None
        nets[svc] = set((c or {}).get("NetworkSettings", {}).get("Networks", {}).keys())
    if nets["frontend"] and nets["db"] and not (nets["frontend"] & nets["db"]):
        got += 0.5
    else:
        notes.append("frontend y db comparten red (o no existen)")
    # depends_on con condition: service_healthy en catalog, orders y worker
    rc, out = lab.compose("config", "--format", "json")
    ok_dep = False
    if rc == 0:
        try:
            services = json.loads(out).get("services", {})
            ok_dep = all(
                any((d or {}).get("condition") == "service_healthy"
                    for d in (services.get(s, {}).get("depends_on") or {}).values())
                for s in ("catalog", "orders", "worker")
            )
        except (ValueError, AttributeError):
            ok_dep = False
    if ok_dep:
        got += 0.5
    else:
        notes.append("catalog, orders y worker deben usar depends_on con condition: service_healthy")
    rep.add("compose_structure", G_QUAL, "Compose: redes separadas y arranque por salud", 1, got, "; ".join(notes))


def check_persistence(lab: Lab, rep: Report, oid):
    if oid is None:
        rep.add("persistence", G_FUNC, "Los datos sobreviven a down/up", 5, 0, "no hay pedido de prueba")
        return
    lab.down()
    rc, out = lab.up(build=False)
    ok, detail = False, "no se pudo volver a levantar"
    if rc == 0:
        wait_http(lab.url("/api/products"), 30)
        status, body = http("GET", lab.url(f"/api/orders/{oid}"))
        ok = status == 200
        detail = "" if ok else f"tras down/up el pedido {oid} ya no existe (¿volumen nombrado?)"
    rep.add("persistence", G_FUNC, "Los datos sobreviven a down/up", 5, 5 if ok else 0, detail)


# --------------------------------------------------------------------------- principal
def run(args) -> Report:
    lab = Lab(args.dir)
    rep = Report(lab.team)
    check_static(lab, rep)
    rep.flags["codigo_de_app_modificado"] = ", ".join(app_code_modified(lab, args.hashes))

    rc, _ = sh(["docker", "version", "--format", "{{.Server.Version}}"], timeout=20)
    docker_ok = rc == 0 and not args.static
    if not docker_ok:
        msg = "modo --static" if args.static else "no se pudo hablar con el daemon de Docker"
        for cid, label, mx, g in (("up", "docker compose up levanta todo", 5, G_FUNC),
                                  ("frontend", "Frontend responde con la página del equipo", 5, G_FUNC),
                                  ("catalog", "Catálogo lee productos de la base de datos", 5, G_FUNC),
                                  ("orders_flow", "Pedido recorre orders → Redis → worker → base de datos", 10, G_FUNC),
                                  ("persistence", "Los datos sobreviven a down/up", 5, G_FUNC),
                                  ("size", "Tamaño de imagen dentro del límite", 4, G_QUAL),
                                  ("nonroot", "Contenedor corre como usuario no root", 4, G_QUAL),
                                  ("healthcheck", "HEALTHCHECK definido", 4, G_QUAL),
                                  ("secrets", "Sin secretos en capas ni en ENV de la imagen", 4, G_QUAL),
                                  ("cache_layers", "Caché de capas: cambiar código no reinstala dependencias", 1, G_QUAL),
                                  ("compose_structure", "Compose: redes separadas y arranque por salud", 1, G_QUAL)):
            rep.add(cid, g, label, mx, 0, f"no evaluado ({msg})")
        return rep

    if args.skip_up:
        up_ok, up_out = True, ""
    else:
        rc, up_out = lab.up()
        up_ok = rc == 0
    oid = check_functional(lab, rep, up_ok, up_out, args.master_secret)
    check_images(lab, rep)
    check_compose_structure(lab, rep)
    if args.no_cache_check:
        rep.add("cache_layers", G_QUAL, "Caché de capas: cambiar código no reinstala dependencias", 1, 0, "omitido (--no-cache-check)")
    else:
        check_cache(lab, rep)
    if up_ok:
        check_persistence(lab, rep, oid)
    else:
        rep.add("persistence", G_FUNC, "Los datos sobreviven a down/up", 5, 0, "el stack no está arriba")
    if args.down:
        lab.down()
    # orden estable: funcionamiento primero
    rep.checks.sort(key=lambda c: (c["group"] != G_FUNC,))
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser(description="Verificador de Operación Despliegue")
    ap.add_argument("--dir", default=".", help="carpeta del repositorio del equipo (def. .)")
    ap.add_argument("--json", help="guardar el informe en este archivo JSON")
    ap.add_argument("--static", action="store_true", help="solo revisiones que no usan Docker")
    ap.add_argument("--skip-up", action="store_true", help="no ejecutar 'compose up' (el stack ya está arriba)")
    ap.add_argument("--no-cache-check", action="store_true", help="omitir la prueba de caché de capas (más rápido)")
    ap.add_argument("--down", action="store_true", help="apagar el stack al terminar")
    ap.add_argument("--master-secret", help="(docente) secreto maestro para validar la identidad del stack")
    ap.add_argument("--hashes", help="(docente) archivo con los hashes originales del código de las apps")
    args = ap.parse_args(argv)

    rep = run(args)
    rep.print()
    if args.json:
        Path(args.json).write_text(json.dumps(rep.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
