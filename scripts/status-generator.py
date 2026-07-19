#!/usr/bin/env python3
"""status-generator.py — Genera status.json unificado para dashboard de salud.
Fusiona datos de infraestructura (Docker, disco, RAM) + negocio (props, tenants, Meili).
Output: /home/polaris/workspace/public/system-health/status.json
Corre cada 5 min desde cron."""

import json
import subprocess
import time
import os
import glob
from datetime import datetime, timezone


def cmd(c, timeout=10):
    try:
        r = subprocess.run(c, capture_output=True, text=True, timeout=timeout, shell=True)
        return r.returncode == 0, r.stdout.strip()
    except Exception:
        return False, ""


result = {
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "generated_at": time.time(),
}

# 1. BACKBONE API
ok, out = cmd("curl -s --max-time 5 http://localhost:8005/health")
if ok:
    try:
        result["backbone"] = json.loads(out)
    except:
        result["backbone"] = {"status": "unhealthy"}
else:
    result["backbone"] = {"status": "unreachable"}

# 2. Docker containers
ok, out = cmd("docker ps --format json 2>/dev/null")
if ok:
    containers = []
    for line in out.strip().split("\n"):
        if line:
            try:
                containers.append(json.loads(line))
            except:
                pass
    result["docker"] = {
        c.get("Names"): {
            "status": c.get("Status", "?"),
            "healthy": "healthy" in c.get("Status", ""),
        }
        for c in containers
    }

# 3. System resources
ok, out = cmd("df -h / --output=target,size,used,avail,pcent 2>/dev/null | tail -1")
if ok:
    parts = out.split()
    if len(parts) >= 5:
        result["disk"] = {
            "total": parts[1],
            "used": parts[2],
            "available": parts[3],
            "usage_pct": parts[4],
        }

ok, out = cmd("free -h 2>/dev/null | grep Mem")
if ok:
    parts = out.split()
    if len(parts) >= 7:
        result["memory"] = {
            "total": parts[1],
            "used": parts[2],
            "available": parts[6],
        }

ok, out = cmd("cat /proc/loadavg 2>/dev/null | cut -d' ' -f1-3")
if ok:
    result["load"] = out.strip()

# 4. Public domains
DOMAINS = [
    "https://back-bone.dev",
    "https://api.back-bone.dev",
    "https://docs.back-bone.dev",
    "https://quasar.back-bone.dev",
    "https://crm.visionnorth.mx",
    "https://padim.enmexico.casa",
    "https://polaris.pw",
    "https://astra.visionnorth.mx",
    "https://workspace.visionnorth.mx",
    "https://grafana.visionnorth.mx",
    "https://prometheus.visionnorth.mx",
    "https://app.thuban.online",
]
result["services"] = {}
for d in DOMAINS:
    name = d.replace("https://", "")
    ok, out = cmd(f"curl -s -o /dev/null -w '%{{http_code}}' --max-time 5 {d}")
    code = int(out) if ok and out.strip().isdigit() else 0
    result["services"][name] = {"http_code": code, "healthy": 200 <= code < 400}

# 5. Business metrics
ok, out = cmd(
    "docker exec backbone-postgres psql -U backbone -d backbone -t -A -c "
    '"SET search_path TO tenant_default; SELECT count(*) FROM properties '
    "WHERE status='active' AND is_deleted=false;\" 2>/dev/null"
)
if ok:
    # Filter out "SET" line
    lines = [l for l in out.strip().split("\n") if l and l != "SET" and l.strip().isdigit()]
    if lines:
        result["properties_db"] = int(lines[-1])

ok, out = cmd(
    "curl -s --max-time 5 -H 'Authorization: Bearer backbone_master_key_dev' "
    "http://localhost:7700/indexes/properties/stats 2>/dev/null"
)
if ok:
    try:
        meili = json.loads(out)
        result["meili_docs"] = meili.get("numberOfDocuments", 0)
        result["meili_last_update"] = meili.get("updatedAt", "")
    except:
        pass

if "properties_db" in result and "meili_docs" in result:
    result["index_gap"] = result["properties_db"] - result["meili_docs"]

# 6. Tenants
ok, out = cmd(
    "docker exec backbone-postgres psql -U backbone -d backbone -t -A -c "
    '"SELECT schema_name FROM information_schema.schemata '
    "WHERE schema_name LIKE 'tenant_%' ORDER BY schema_name;\" 2>/dev/null"
)
if ok:
    tenants = [t.strip() for t in out.strip().split("\n") if t.strip() and t.strip() != "SET"]
    result["tenants"] = {}
    for t in tenants:
        label = t.replace("tenant_", "")
        ok2, count = cmd(
            f"docker exec backbone-postgres psql -U backbone -d backbone -t -A -c "
            f'"SET search_path TO {t}; SELECT count(*) FROM properties;" 2>/dev/null'
        )
        if ok2 and count.strip():
            lines = [l for l in count.strip().split("\n") if l.strip() and l.strip() != "SET" and l.strip().isdigit()]
            if lines:
                result["tenants"][label] = int(lines[-1])

# 7. Last scrape freshness
files = sorted(
    glob.glob(
        "/home/polaris/workspace/projects/BACKBONE/data/vivanuncios_*.jsonl"
    ),
    key=os.path.getmtime,
)
if files:
    newest = max(files, key=os.path.getmtime)
    age_hours = (time.time() - os.path.getmtime(newest)) / 3600
    result["last_scrape_hours"] = round(age_hours, 1)

# 8. Backup age
bkp = sorted(
    glob.glob("/home/polaris/hermes-data/backups/postgres/*backbone_*.sql.gz"),
    key=os.path.getmtime,
)
if bkp:
    newest = max(bkp, key=os.path.getmtime)
    age_days = (time.time() - os.path.getmtime(newest)) / 86400
    result["backup_age_days"] = round(age_days, 1)

# 9. Health score
score = 100
alerts = []

if result.get("backbone", {}).get("status") != "ok":
    score -= 20
    alerts.append("BACKBONE API caida")

if result.get("index_gap", 0) > 10000:
    score -= 15
    alerts.append(f"Gap DB-Meili: {result['index_gap']}")

if result.get("last_scrape_hours", 0) > 6:
    score -= 10
    alerts.append(f"Scraping stale ({result['last_scrape_hours']}h)")

if result.get("backup_age_days", 0) > 2:
    score -= 15
    alerts.append(f"Backups caidos ({result['backup_age_days']} dias)")

bad_domains = {
    k for k, v in result.get("services", {}).items() if not v["healthy"]
}
if bad_domains:
    score -= 5 * len(bad_domains)
    alerts.append(f"Dominios caidos: {', '.join(list(bad_domains)[:3])}")

result["health_score"] = max(0, score)
if score >= 90:
    result["traffic_light"] = "green"
elif score >= 70:
    result["traffic_light"] = "yellow"
else:
    result["traffic_light"] = "red"

result["alerts"] = alerts
result["uptime"] = cmd("uptime -p")[1] or ""

# Save
os.makedirs("/home/polaris/workspace/public/system-health", exist_ok=True)
with open("/home/polaris/workspace/public/system-health/status.json", "w") as f:
    json.dump(result, f, indent=2, default=str)

print(f"status.json generado - score={score}, alerts={len(alerts)}")