#!/usr/bin/env python3
"""
🧬 system-health-collector.py — Recolecta estado del ecosistema 3x/día.
Genera /home/polaris/workspace/public/system-health/status.json

Ejecutar vía cronjob cada 8h (o más frecuente si se desea).
"""
import json, subprocess, os, socket, time
from datetime import datetime, timezone
from pathlib import Path

OUTPUT = Path("/home/polaris/workspace/public/system-health")
OUTPUT.mkdir(parents=True, exist_ok=True)

def run(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return "(timeout)", -1
    except Exception as e:
        return str(e), -1

def collect():
    ts = datetime.now(timezone.utc).isoformat()
    data = {"timestamp": ts, "generated_at": time.time()}

    # ── 1. BACKBONE API ──────────────────────────────────────
    bb_out, bb_code = run("curl -s --max-time 5 http://localhost:8005/health")
    if bb_code == 0 and bb_out:
        try:
            bb = json.loads(bb_out)
            data["backbone"] = {
                "status": bb.get("status", "unknown"),
                "version": bb.get("version", "?"),
                "database": bb.get("database", "unknown"),
                "meilisearch": bb.get("meilisearch", "unknown"),
                "redis": bb.get("redis", "unknown"),
                "scraping": bb.get("scraping", "unknown"),
            }
        except json.JSONDecodeError:
            data["backbone"] = {"status": "error", "raw": bb_out[:200]}
    else:
        data["backbone"] = {"status": "unreachable"}

    # ── 2. Docker containers ─────────────────────────────────
    dock_out, _ = run("docker ps --format '{{.Names}}\t{{.Status}}' --no-trunc")
    containers = {}
    for line in dock_out.split("\n"):
        if "\t" in line:
            name, status = line.split("\t", 1)
            healthy = "healthy" in status.lower() or "up" in status.lower()
            containers[name] = {"status": status.strip(), "healthy": healthy}
    data["docker"] = containers

    # ── 3. Disco ─────────────────────────────────────────────
    disk_out, _ = run("df -h / | tail -1")
    parts = disk_out.split()
    if len(parts) >= 5:
        data["disk"] = {
            "total": parts[1],
            "used": parts[2],
            "available": parts[3],
            "usage_pct": parts[4],
        }

    # ── 4. Memoria ───────────────────────────────────────────
    mem_out, _ = run("free -h | grep Mem")
    parts = mem_out.split()
    if len(parts) >= 3:
        data["memory"] = {
            "total": parts[1],
            "used": parts[2],
            "available": parts[4] if len(parts) > 4 else "?",
        }

    # ── 5. Load ──────────────────────────────────────────────
    load_out, _ = run("uptime")
    if "load average" in load_out:
        load = load_out.split("load average:")[-1].strip()
        data["load"] = load

    # ── 6. Servicios HTTP externos ───────────────────────────
    endpoints = {
        "api.back-bone.dev": "https://api.back-bone.dev/health",
        "workspace.visionnorth.mx": "https://workspace.visionnorth.mx/",
        "polaris.pw": "https://polaris.pw/",
        "webui.visionnorth.mx": "https://webui.visionnorth.mx/",
        "grafana.visionnorth.mx": "https://grafana.visionnorth.mx/",
        "prometheus.visionnorth.mx": "https://prometheus.visionnorth.mx/",
    }
    services = {}
    for name, url in endpoints.items():
        out, code = run(f'curl -s -o /dev/null -w "%{{http_code}}" --max-time 5 "{url}"')
        if code == 0 and out:
            code_int = int(out) if out.isdigit() else 0
            ok = 200 <= code_int < 400
            services[name] = {"http_code": code_int, "healthy": ok}
        else:
            services[name] = {"http_code": 0, "healthy": False, "error": "timeout/no route"}
    data["services"] = services

    # ── 7. EPDS errores activos ─────────────────────────────
    epds_file = Path("/home/polaris/workspace/projects/ERRORES/REGISTRO-ACTIVO.md")
    data["epds"] = {"criticos": 0, "medios": 0, "bajos": 0}
    if epds_file.exists():
        text = epds_file.read_text()
        # Parsear la tabla de métricas: | Errores (tipo) | VALOR | Objetivo | 🟢 |
        import re
        m_activos = re.search(r'\|\s*Errores activos totales\s*\|\s*(\d+)', text)
        m_criticos = re.search(r'\|\s*Errores críticos\s*\|\s*(\d+)', text)
        m_medios = re.search(r'\|\s*Errores medios\s*\|\s*(\d+)', text)
        m_bajos = re.search(r'\|\s*Errores bajos\s*\|\s*(\d+)', text)
        if m_activos: data["epds"]["activos"] = int(m_activos.group(1))
        if m_criticos: data["epds"]["criticos"] = int(m_criticos.group(1))
        if m_medios: data["epds"]["medios"] = int(m_medios.group(1))
        if m_bajos: data["epds"]["bajos"] = int(m_bajos.group(1))

    # ── 8. Cron jobs (Hermes) ────────────────────────────────
    cron_out, _ = run("hermes cron list 2>/dev/null")
    cron_lines = [l.strip() for l in cron_out.split("\n") if l.strip()]
    errored_jobs = sum(1 for l in cron_lines if "error" in l.lower())
    ok_jobs = sum(1 for l in cron_lines if "ok" in l.lower())
    data["cron"] = {
        "total_jobs": len([l for l in cron_lines if "active" in l.lower() or "error" in l.lower() or "ok" in l.lower()]),
        "errored": errored_jobs,
        "ok": ok_jobs,
    }

    # ── 9. Procesos zombie ──────────────────────────────────
    zombie_out, _ = run("ps aux | grep -c '[d]efunct'")
    data["zombies"] = int(zombie_out) if zombie_out.isdigit() else 0

    # ── 10. Uptime del servidor ──────────────────────────────
    up_out, _ = run("uptime -p")
    data["uptime"] = up_out.replace("up ", "") if up_out else "?"

    # Score de salud general (0-100)
    score = 100
    if data.get("backbone", {}).get("status") != "ok":
        score -= 20
    for svc, info in data.get("services", {}).items():
        if not info.get("healthy", True):
            score -= 5
    for c_name, c_info in data.get("docker", {}).items():
        if not c_info.get("healthy", True):
            score -= 10
    if data.get("zombies", 0) > 0:
        score -= 5
    if data.get("cron", {}).get("errored", 0) > 0:
        score -= 10
    data["health_score"] = max(0, min(100, score))

    # Semáforo
    if score >= 90:
        data["traffic_light"] = "green"
    elif score >= 70:
        data["traffic_light"] = "yellow"
    else:
        data["traffic_light"] = "red"

    return data

if __name__ == "__main__":
    data = collect()
    path = OUTPUT / "status.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"[✅] Health snapshot saved: {path}")
    print(f"    Score: {data['health_score']}/100 — {data['traffic_light'].upper()}")

    # NOTA: HTML dashboard ya no se genera desde el collector.
    # index.html es un dashboard dinámico JS que lee status.json.
    # El botón Refresh llama a /api/health/refresh que ejecuta este script.
    # Solo se genera status.json — el HTML dinámico vive en public/system-health/index.html
