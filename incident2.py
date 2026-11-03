#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Incidente 2 — Vulnerabilidad en las imágenes base (simulada).

Todas las imágenes de Python deben usar la versión 3.13 o superior y las de Node la 22 o superior,
con el tag escrito de forma explícita en cada FROM. El stack debe seguir funcionando.
Uso (desde la raíz del repositorio del equipo):
    python3 incident2.py
"""
import argparse
import datetime
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MIN_PYTHON = (3, 13)
MIN_NODE = 22
SERVICES = ["frontend", "catalog", "orders", "worker"]


def _import_verify(team_dir: Path):
    for cand in (HERE, HERE.parent.parent / "template" / "tools", team_dir / "tools"):
        if (cand / "verify.py").exists():
            sys.path.insert(0, str(cand))
            import verify  # noqa: E402
            return verify
    sys.exit("No encuentro tools/verify.py")


def base_images(dockerfile_text: str):
    """Devuelve las imágenes base (FROM) que no son alias de una etapa anterior."""
    aliases, images = set(), []
    for line in dockerfile_text.splitlines():
        m = re.match(r"^\s*FROM\s+(?:--platform=\S+\s+)?(\S+)(?:\s+AS\s+(\S+))?", line, flags=re.IGNORECASE)
        if not m:
            continue
        image, alias = m.group(1), m.group(2)
        if image.lower() not in aliases and image.lower() != "scratch":
            images.append(image)
        if alias:
            aliases.add(alias.lower())
    return images


def violations(image: str):
    """Motivo por el que una imagen base incumple el requisito, o None."""
    if "$" in image:
        return f"{image}: usa una variable; escribe el tag explícito en el FROM"
    name, _, tag = image.partition(":")
    name = name.split("/")[-1].split("@")[0]
    if name == "python":
        m = re.match(r"^(\d+)\.(\d+)", tag)
        if not m or (int(m.group(1)), int(m.group(2))) < MIN_PYTHON:
            return f"{image}: se requiere python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} o superior"
    elif name == "node":
        m = re.match(r"^(\d+)", tag)
        if not m or int(m.group(1)) < MIN_NODE:
            return f"{image}: se requiere node {MIN_NODE} o superior"
    return None


def run(directory: str, write_evidence: bool):
    v = _import_verify(Path(directory))
    lab = v.Lab(directory)
    problems = []

    for svc in SERVICES:
        f = lab.dir / svc / "Dockerfile"
        if not f.exists():
            problems.append(f"falta {svc}/Dockerfile")
            continue
        for image in base_images(f.read_text(encoding="utf-8", errors="replace")):
            why = violations(image)
            if why:
                problems.append(f"{svc}/Dockerfile → {why}")

    rc, out = lab.up()
    if rc != 0:
        problems.append("el stack no levanta: " + (out.strip().splitlines()[-1][:120] if out.strip() else ""))
    else:
        v.wait_http(lab.url("/api/products"), 30)
        ok, detail, _ = v.order_flow(lab)
        if not ok:
            problems.append("el flujo de pedidos falla: " + detail)

    ok = not problems
    if ok and write_evidence:
        ev = Path(directory) / ".lab" / "evidence"
        ev.mkdir(parents=True, exist_ok=True)
        (ev / "incident-2.json").write_text(json.dumps({
            "incident": 2, "team": lab.team,
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
    print("INCIDENTE 2:", "RESUELTO" if ok else "PENDIENTE")
    for p in problems:
        print("  -", p)
    if args.json:
        Path(args.json).write_text(json.dumps({"incident": 2, "ok": ok, "problems": problems}), encoding="utf-8")
    if args.down:
        lab.down()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
