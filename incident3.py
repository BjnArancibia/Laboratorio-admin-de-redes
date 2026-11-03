#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Incidente 3 — Servicio caído (Redis).

El script levanta el stack, mata el contenedor de Redis (SIGKILL) y comprueba que el sistema
se recupera solo: Redis vuelve a estar en pie y un pedido nuevo se procesa de punta a punta.
Uso (desde la raíz del repositorio del equipo):
    python3 incident3.py
"""
import argparse
import datetime
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
RECOVERY_SECONDS = 60


def _import_verify(team_dir: Path):
    for cand in (HERE, HERE.parent.parent / "template" / "tools", team_dir / "tools"):
        if (cand / "verify.py").exists():
            sys.path.insert(0, str(cand))
            import verify  # noqa: E402
            return verify
    sys.exit("No encuentro tools/verify.py")


def cache_running(lab):
    cid = lab.cid("cache")
    c = lab.inspect(cid) if cid else None
    if not c:
        return False
    state = c.get("State", {})
    if not state.get("Running"):
        return False
    health = state.get("Health")
    return health is None or health.get("Status") == "healthy"


def run(directory: str, write_evidence: bool):
    v = _import_verify(Path(directory))
    lab = v.Lab(directory)
    problems = []

    rc, out = lab.up()
    if rc != 0:
        problems.append("el stack no levanta: " + (out.strip().splitlines()[-1][:120] if out.strip() else ""))
        return False, problems, lab
    v.wait_http(lab.url("/api/products"), 30)

    # el incidente: Redis cae de golpe
    lab.compose("kill", "-s", "SIGKILL", "cache", timeout=60)
    time.sleep(2)
    end = time.time() + RECOVERY_SECONDS
    recovered = False
    while time.time() < end:
        if cache_running(lab):
            recovered = True
            break
        time.sleep(2)
    if not recovered:
        problems.append(f"Redis no volvió a estar en pie en {RECOVERY_SECONDS}s (¿qué le falta al servicio cache?)")
        return False, problems, lab

    ok, detail, _ = v.order_flow(lab, timeout=40)
    if not ok:
        problems.append("tras la caída, el flujo de pedidos no se recuperó: " + detail)

    ok = not problems
    if ok and write_evidence:
        ev = Path(directory) / ".lab" / "evidence"
        ev.mkdir(parents=True, exist_ok=True)
        (ev / "incident-3.json").write_text(json.dumps({
            "incident": 3, "team": lab.team,
            "solved_at": datetime.datetime.now(datetime.timezone.utc).isoformat()}), encoding="utf-8")
    return ok, problems, lab


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=".")
    ap.add_argument("--json")
    ap.add_argument("--no-evidence", action="store_true")
    ap.add_argument("--down", action="store_true")
    args = ap.parse_args()
    ok, problems, lab = run(args.dir, not args.no_evidence)
    print("INCIDENTE 3:", "RESUELTO" if ok else "PENDIENTE")
    for p in problems:
        print("  -", p)
    if args.json:
        Path(args.json).write_text(json.dumps({"incident": 3, "ok": ok, "problems": problems}), encoding="utf-8")
    if args.down:
        lab.down()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
