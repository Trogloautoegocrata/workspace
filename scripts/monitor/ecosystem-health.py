"""
ECOSYSTEM HEALTH MONITOR — OmegaBridge Intelligence Layer
v1.0.0 — Julio 2026

Monitorea todos los servicios del ecosistema VisionNorth.
Se ejecuta como cron cada 5 minutos.
Reporta SOLO cambios de estado a OmegaBridge (silencio si todo bien).

Modo de operación:
  - Cache de estado anterior en /tmp/ecosystem-health-cache.json
  - Solo reporta si el estado CAMBIÓ desde la última ejecución
  - Reporta errores con severidad: 🔴 CRITICAL / 🟡 WARNING / ✅ OK
"""

import subprocess
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta

# ─── Configuración ───────────────────────────────────────────────────────────

CACHE_FILE = "/tmp/ecosystem-health-cache.json"
BACKBONE_DIR = "/home/polaris/workspace/projects/BACKBONE"

SERVICES = {
    "backbone_api": {
        "name": "BACKBONE API",
        "check": "http",
        "url": "http://localhost:8005/health",
        "expected": '"status":"ok"',
        "severity": "CRITICAL"
    },
    "postgresql": {
        "name": "PostgreSQL",
        "check": "pg",
        "host": "localhost",
        "port": 5432,
        "db": "backbone",
        "user": "backbone",
        "password": "backbone_dev_pass",
        "severity": "CRITICAL"
    },
    "meilisearch": {
        "name": "Meilisearch",
        "check": "http",
        "url": "http://localhost:7700/health",
        "expected": '"status":"available"',
        "severity": "CRITICAL"
    },
    "redis": {
        "name": "Redis",
        "check": "redis_ping",
        "host": "localhost",
        "port": 6379,
        "password": "backbone_redis_dev",
        "severity": "CRITICAL"
    },
    "celery_worker": {
        "name": "Celery Worker",
        "check": "systemd",
        "service": "backbone-celery",
        "severity": "CRITICAL"
    },
    "caddy": {
        "name": "Caddy",
        "check": "systemd",
        "service": "caddy",
        "severity": "HIGH"
    },
    "nginx": {
        "name": "Nginx",
        "check": "systemd",
        "service": "nginx",
        "severity": "HIGH"
    },
    "agente_soporte": {
        "name": "Agente Soporte",
        "check": "http",
        "url": "http://localhost:8088/health",
        "expected": '"status":"ok"',
        "severity": "HIGH"
    },
    "ghl_mcp": {
        "name": "GHL MCP",
        "check": "systemd",
        "service": "mcp-ghl",
        "severity": "MEDIUM"
    },
}

DATA_CHECKS = {
    "properties_db": {
        "name": "Propiedades en DB",
        "description": "Total properties en tenant_default",
        "warn_below": 100000,
        "critical_below": 50000,
        "query": "SET search_path TO tenant_default; SELECT count(*) FROM properties;"
    },
    "meili_freshness": {
        "name": "Meilisearch Freshness",
        "description": "Días desde último index",
        "warn_above": 3,
        "critical_above": 7,
        "query": None  # Se obtiene de API de Meili
    },
    "last_scrape": {
        "name": "Último Scrape",
        "description": "Horas desde último archivo JSONL",
        "warn_above": 8,
        "critical_above": 24,
        "check": "file_age",
        "pattern": "/home/polaris/workspace/projects/BACKBONE/data/vivanuncios_*.jsonl"
    },
    "backup_age": {
        "name": "Backups",
        "description": "Días desde último backup de PostgreSQL",
        "warn_above": 2,
        "critical_above": 3,
        "check": "dir_age",
        "pattern": "/home/polaris/hermes-data/backups/postgres/backbone_*.sql.gz"
    },
    "disk_usage": {
        "name": "Disco",
        "description": "Uso de disco %",
        "warn_above": 80,
        "critical_above": 90,
        "check": "disk"
    },
}

PUBLIC_DOMAINS = [
    "https://back-bone.dev",
    "https://api.back-bone.dev",
    "https://docs.back-bone.dev",
    "https://quasar.back-bone.dev",
    "https://crm.visionnorth.mx",
    "https://padim.enmexico.casa",
    "https://polaris.pw",
    "https://astra.visionnorth.mx",
]


def load_cache() -> dict:
    """Carga el estado anterior del cache."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_cache(state: dict):
    """Guarda el estado actual en cache."""
    state["_last_check"] = datetime.now(timezone.utc).isoformat()
    os.makedirs(os.path.dirname(CACHE_FILE) or "/tmp", exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump(state, f, indent=2, default=str)


def check_command(cmd: list, timeout: int = 10) -> tuple:
    """Ejecuta comando y retorna (success, output)."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode == 0, result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return False, str(e)


# ─── Checkers específicos ────────────────────────────────────────────────────

def check_http(url: str, expected_substr: str, timeout: int = 5) -> tuple:
    ok, out = check_command(["curl", "-s", "--max-time", str(timeout), url])
    if not ok:
        return False, f"no response"
    if expected_substr in out:
        return True, "ok"
    return False, f"unexpected: {out[:100]}"


def check_systemd(service: str) -> tuple:
    ok, out = check_command(["systemctl", "is-active", service])
    if ok and "active" in out:
        return True, "active"
    return False, out or "inactive"


def check_redis_ping(host: str, port: int, password: str) -> tuple:
    ok, out = check_command([
        "redis-cli", "-h", host, "-p", str(port), "-a", password, "ping"
    ], timeout=5)
    if ok and "PONG" in out:
        return True, "PONG"
    return False, out or "no response"


def check_pg(db: str, user: str, password: str, host: str, port: int) -> tuple:
    """Check PostgreSQL via docker exec (psql inside container)."""
    ok, out = check_command([
        "docker", "exec", "backbone-postgres", "psql", "-U", user, "-d", db,
        "-c", "SELECT 1 as alive;"
    ], timeout=5)
    if ok and "1" in out:
        return True, "connected"
    return False, out[:100] or "no response"


def check_systemd_service(service_name: str) -> tuple:
    ok, out = check_command(["systemctl", "is-active", service_name])
    return (True, "active") if ok and "active" in out else (False, out or "inactive")


def check_disk() -> tuple:
    ok, out = check_command(["df", "-h", "/", "--output=pcent"], timeout=5)
    if not ok:
        return False, 0
    try:
        pct = int(out.split("\n")[-1].strip().replace("%", ""))
        return True, pct
    except (ValueError, IndexError):
        return False, 0


def check_file_age(pattern: str) -> tuple:
    import glob
    files = glob.glob(pattern)
    if not files:
        return False, 999  # No files = critical
    
    newest = max(files, key=os.path.getmtime)
    age_hours = (time.time() - os.path.getmtime(newest)) / 3600
    return True, int(age_hours)


def check_dir_age(pattern: str) -> tuple:
    import glob
    items = glob.glob(pattern)
    if not items:
        return False, 999
    
    newest = max(items, key=os.path.getmtime)
    age_days = (time.time() - os.path.getmtime(newest)) / 86400
    return True, int(age_days)


def get_meili_stats() -> dict:
    """Obtiene stats de Meilisearch."""
    meili_key = "backbone_master_key_dev"
    ok, out = check_command([
        "curl", "-s", "--max-time", "5",
        "-H", f"Authorization: Bearer {meili_key}",
        "http://localhost:7700/indexes/properties/stats"
    ])
    if not ok:
        return {"error": "no response"}
    try:
        data = json.loads(out)
        docs = data.get("numberOfDocuments", 0)
        updated = data.get("updatedAt", "")
        if updated:
            updated_dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
            days_stale = (datetime.now(timezone.utc) - updated_dt).days
            return {"docs": docs, "last_update": updated, "days_stale": days_stale}
        return {"docs": docs}
    except (json.JSONDecodeError, ValueError):
        return {"error": "parse_failed"}


def run_checks() -> dict:
    """Ejecuta todas las verificaciones y retorna el estado."""
    results = {"services": {}, "data": {}, "alerts": [], "timestamp": datetime.now(timezone.utc).isoformat()}
    
    # ── Servicios ──
    for service_id, config in SERVICES.items():
        try:
            if config["check"] == "http":
                ok, detail = check_http(config["url"], config["expected"])
            elif config["check"] == "systemd":
                ok, detail = check_systemd_service(config["service"])
            elif config["check"] == "redis_ping":
                ok, detail = check_redis_ping(config["host"], config["port"], config["password"])
            elif config["check"] == "pg":
                ok, detail = check_pg(config["db"], config["user"], config["password"], config["host"], config["port"])
            else:
                ok, detail = False, "unknown check type"
            
            results["services"][service_id] = {
                "name": config["name"],
                "status": "ok" if ok else "error",
                "detail": detail,
                "severity": config["severity"],
            }
            
            if not ok:
                alert = f"[{config['severity']}] {config['name']}: {detail}"
                results["alerts"].append(alert)
                
        except Exception as e:
            results["services"][service_id] = {
                "name": config["name"],
                "status": "error",
                "detail": str(e)[:100],
                "severity": config["severity"],
            }
            results["alerts"].append(f"[{config['severity']}] {config['name']}: {str(e)[:100]}")
    
    # ── Datos ──
    # Propiedades en DB
    ok, out = check_command([
        "docker", "exec", "backbone-postgres", "psql", "-U", "backbone",
        "-d", "backbone", "-t", "-A",
        "-c", "SET search_path TO tenant_default; SELECT count(*) FROM properties;"
    ], timeout=5)
    if ok and out.strip().isdigit():
        props_db = int(out.strip())
        results["data"]["properties_db"] = props_db
        if props_db < 50000:
            results["alerts"].append(f"[HIGH] Propiedades en DB: {props_db} (crítico < 50K)")
    
    # Meilisearch stats
    meili = get_meili_stats()
    if "error" not in meili:
        results["data"]["meili_docs"] = meili.get("docs", 0)
        stale = meili.get("days_stale", 0)
        results["data"]["meili_stale_days"] = stale
        if stale > 7:
            results["alerts"].append(f"[HIGH] Meilisearch no actualizado hace {stale} días")
        elif stale > 3:
            results["alerts"].append(f"[MEDIUM] Meilisearch desactualizado ({stale} días)")
    
    # Gap DB vs Meili
    if "properties_db" in results["data"] and "meili_docs" in results["data"]:
        gap = results["data"]["properties_db"] - results["data"]["meili_docs"]
        results["data"]["index_gap"] = gap
        if gap > 10000:
            results["alerts"].append(f"[MEDIUM] Gap DB-Meili: {gap} propiedades sin indexar")
    
    # Último scrape
    ok, age_hours = check_file_age("/home/polaris/workspace/projects/BACKBONE/data/vivanuncios_*.jsonl")
    if ok:
        results["data"]["last_scrape_hours"] = age_hours
        if age_hours > 12:
            results["alerts"].append(f"[HIGH] Sin scraping nuevo en {age_hours}h")
        elif age_hours > 6:
            results["alerts"].append(f"[MEDIUM] Scraping retrasado ({age_hours}h)")
    
    # Backups
    ok, age_days = check_dir_age("/home/polaris/hermes-data/backups/postgres/backbone_*.sql.gz")
    if ok:
        results["data"]["backup_age_days"] = age_days
        if age_days > 14:
            results["alerts"].append(f"[HIGH] Backups caídos hace {age_days} días")
        elif age_days > 7:
            results["alerts"].append(f"[MEDIUM] Backups hace {age_days} días")
    
    # Disco
    ok, pct = check_disk()
    if ok:
        results["data"]["disk_usage_pct"] = pct
        if pct > 90:
            results["alerts"].append(f"[CRITICAL] Disco al {pct}%")
        elif pct > 80:
            results["alerts"].append(f"[MEDIUM] Disco al {pct}%")
    
    # Tenants
    ok, out = check_command([
        "docker", "exec", "backbone-postgres", "psql", "-U", "backbone",
        "-d", "backbone", "-t", "-A",
        "-c", "SELECT schema_name FROM information_schema.schemata WHERE schema_name LIKE 'tenant_%' ORDER BY schema_name;"
    ], timeout=5)
    if ok:
        tenants = [t.strip() for t in out.split("\n") if t.strip()]
        results["data"]["tenants"] = tenants
        # Check each tenant has data
        for t_name in tenants:
            ok2, t_count = check_command([
                "docker", "exec", "backbone-postgres", "psql", "-U", "backbone",
                "-d", "backbone", "-t", "-A",
                "-c", f"SET search_path TO {t_name}; SELECT count(*) FROM properties;"
            ], timeout=5)
            if ok2 and t_count.strip().isdigit():
                if int(t_count.strip()) == 0 and t_name != "tenant_default":
                    results["alerts"].append(f"[MEDIUM] Tenant {t_name} vacío (0 propiedades)")
    
    # Dominios públicos
    results["data"]["public_domains"] = {}
    for url in PUBLIC_DOMAINS:
        ok, _ = check_command(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "5", url])
        code = int(ok) if ok else 0
        results["data"]["public_domains"][url] = code
    
    # Resumen
    total_services = len(results["services"])
    ok_count = sum(1 for s in results["services"].values() if s["status"] == "ok")
    results["summary"] = {
        "total_services": total_services,
        "healthy": ok_count,
        "unhealthy": total_services - ok_count,
        "alerts_count": len(results["alerts"]),
    }
    
    # Estado general
    if results["alerts"]:
        critical = [a for a in results["alerts"] if "[CRITICAL]" in a]
        high = [a for a in results["alerts"] if "[HIGH]" in a]
        if critical:
            results["overall_status"] = "CRITICAL"
        elif high:
            results["overall_status"] = "DEGRADED"
        else:
            results["overall_status"] = "WARNING"
    else:
        results["overall_status"] = "HEALTHY"
    
    return results


def main():
    """Ejecuta checks y reporta solo cambios a OmegaBridge."""
    
    previous = load_cache()
    current = run_checks()
    
    # Comparar con estado anterior
    prev_status = previous.get("overall_status", "unknown")
    curr_status = current["overall_status"]
    
    prev_alerts = set(previous.get("alerts", []))
    curr_alerts = set(current["alerts"])
    
    new_alerts = curr_alerts - prev_alerts
    resolved_alerts = prev_alerts - curr_alerts
    
    # Siempre guardar cache
    save_cache({
        "overall_status": curr_status,
        "alerts": list(curr_alerts),
        "summary": current["summary"],
        "data": {k: v for k, v in current["data"].items() if isinstance(v, (int, str, list))},
    })
    
    # ── Reportar solo cambios ──
    status_emoji = {
        "HEALTHY": "✅",
        "WARNING": "🟡",
        "DEGRADED": "⚠️",
        "CRITICAL": "🔴",
    }
    
    lines = []
    
    # Si el estado cambió, reportar completo
    if prev_status != curr_status or "unknown" in str(prev_status):
        lines.append(f"{status_emoji.get(curr_status, '❓')} Ecosistema: {curr_status}")
        lines.append(f"   Servicios: {current['summary']['healthy']}/{current['summary']['total_services']} saludables")
        if current['alerts']:
            lines.append("")
            lines.append("⚠️ Alertas:")
            for alert in current['alerts']:
                lines.append(f"   {alert}")
        if 'data' in current:
            d = current['data']
            lines.append("")
            lines.append("📊 Métricas:")
            if "properties_db" in d:
                lines.append(f"   Propiedades DB: {d.get('properties_db','?'):,}")
            if "meili_docs" in d:
                lines.append(f"   Meilisearch docs: {d.get('meili_docs','?'):,}")
            if "last_scrape_hours" in d:
                lines.append(f"   Último scrape: {d['last_scrape_hours']}h atrás")
            if "backup_age_days" in d:
                lines.append(f"   Último backup: {d['backup_age_days']} días")
            if "disk_usage_pct" in d:
                lines.append(f"   Disco: {d['disk_usage_pct']}%")
    
    # Si hay nuevas alertas desde la última vez
    elif new_alerts:
        lines.append(f"🚨 Nuevas alertas detectadas:")
        for alert in sorted(new_alerts):
            lines.append(f"   {alert}")
    
    # Si se resolvieron alertas
    elif resolved_alerts:
        lines.append(f"✅ Alertas resueltas:")
        for alert in sorted(resolved_alerts):
            lines.append(f"   {alert}")
    
    # Si todo sigue igual y está bien → SILENCIO
    else:
        return  # No output = no notification
    
    # SALIDA
    print("\n".join(lines))


if __name__ == "__main__":
    main()
