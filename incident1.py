#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Incidente 1 — Cambio de requisito (solo configuración).

Se entrega a los equipos junto con card1.md en el momento del anuncio.
Uso (desde la raíz del repositorio del equipo):
    python3 incident1.py            # verifica y, si pasa, registra la hora de resolución
"""
import argparse
import datetime
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CURRENCIES = ["CLP", "EUR", "BRL", "MXN"]  # moneda = CURRENCIES[numero_de_equipo % 4]
PORT_BASE = 19000                           # puerto nuevo = 19000 + numero_de_equipo


def _import_verify(team_dir: Path):
    for cand in (HERE, HERE.parent.parent / "template" / "tools", team_dir / "tools"):
        if (cand / "verify.py").exists():
            sys.path.insert(0, str(cand))
            import verify  # noqa: E402
            return verify
    sys.exit("No encuentro tools/verify.py")


def team_number(team_id: str) -> int:
    digits = "".join(ch for ch in team_id if ch.isdigit())
    return int(digits) if digits else 0


def params(team_id: str):
    n = team_number(team_id)
    return PORT_BASE + n, CURRENCIES[n % 4]


def run(directory: str, write_evidence: bool, hashes=None):
    v = _import_verify(Path(directory))
    lab = v.Lab(directory)
    port, currency = params(lab.team)
    problems = []

    changed = [f for f in v.app_code_modified(lab, hashes) if f == "catalog/app/main.py"]
    if changed:
        problems.append("se modificó catalog/app/main.py; el cambio debe hacerse solo con configuración")

    rc, out = lab.up()
    if rc != 0:
        problems.append("el stack no levanta: " + (out.strip().splitlines()[-1][:120] if out.strip() else ""))
    else:
        status, body = v.wait_http(lab.url("/api/products", port), 30)
        if status != 200:
            problems.append(f"GET http://127.0.0.1:{port}/api/products respondió {status}")
        else:
            try:
                items = json.loads(body)
                bad = [i for i in items if i.get("currency") != currency]
                if not items or bad:
                    problems.append(f"los precios deben mostrarse en {currency}")
            except ValueError:
                problems.append("la respuesta de /api/products no es JSON")

    ok = not problems
    if ok and write_evidence:
        ev = Path(directory) / ".lab" / "evidence"
        ev.mkdir(parents=True, exist_ok=True)
        (ev / "incident-1.json").write_text(json.dumps({
            "incident": 1, "team": lab.team,
            "solved_at": datetime.datetime.now(datetime.timezone.utc).isoformat()}), encoding="utf-8")
    return ok, problems, lab


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=".")
    ap.add_argument("--json", help="guardar resultado en JSON")
    ap.add_argument("--no-evidence", action="store_true", help="(docente) no escribir la hora de resolución")
    ap.add_argument("--down", action="store_true")
    ap.add_argument("--hashes", help="(docente) hashes originales del código de las apps")
    args = ap.parse_args()
    ok, problems, lab = run(args.dir, not args.no_evidence, args.hashes)
    print("INCIDENTE 1:", "RESUELTO" if ok else "PENDIENTE")
    for p in problems:
        print("  -", p)
    if args.json:
        Path(args.json).write_text(json.dumps({"incident": 1, "ok": ok, "problems": problems}), encoding="utf-8")
    if args.down:
        lab.down()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
