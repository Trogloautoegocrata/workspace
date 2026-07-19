#!/usr/bin/env python3
"""
🌌 Vía Láctea — Generador de Snapshot Automático del Ecosistema

Propósito: Genera un STATUS/YYYY-MM-DD.md con métricas en vivo del ecosistema.
Uso: python3 via-lactea-snapshot.py [--output-dir /ruta]
Requiere: curl, ss, systemctl (comandos disponibles en el servidor)
"""

import subprocess
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
import re

# === CONFIGURACIÓN ===
WORKSPACE = Path(os.environ.get('HERMES_WORKSPACE', '/home/polaris/workspace'))
OUTPUT_DIR = WORKSPACE / 'projects' / 'STATUS'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MEX_TZ = timezone(timedelta(hours=-6))
TODAY = datetime.now(MEX_TZ).strftime('%Y-%m-%d')
OUTPUT_FILE = OUTPUT_DIR / f'{TODAY}.md'

# === UTILIDADES ===

def run(cmd, timeout=10):
    """Ejecuta comando y devuelve stdout o 'error'."""
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() if r.stdout else f'(exit: {r.returncode})'
    except subprocess.TimeoutExpired:
        return '(timeout)'
    except Exception as e:
        return f'(error: {e})'


def check_service(name):
    """Verifica si un servicio systemd está activo."""
    out = run(f'systemctl is-active {name} 2>/dev/null')
    return '✅ Activo' if out == 'active' else f'❌ {out}'


def check_port(port):
    """Verifica si un puerto está en escucha."""
    out = run(f'ss -tlnp 2>/dev/null | grep -c ":{port} "')
    return '✅ Abierto' if out.strip() and int(out.strip()) > 0 else '❌ Cerrado'


def get_uptime_docker(container):
    """Obtiene uptime de contenedor Docker."""
    out = run(f'docker inspect --format="{{{{.State.Status}}}}|{{{{.State.StartedAt}}}}" {container} 2>/dev/null')
    if '|' in out:
        status, started = out.split('|')
        if status == 'running':
            started_dt = datetime.fromisoformat(started.replace('Z', '+00:00'))
            delta = datetime.now(timezone.utc) - started_dt
            days = delta.days
            hours = delta.seconds // 3600
            return f'✅ Up {days}d {hours}h' if days > 0 else f'✅ Up {hours}h'
        return f'❌ {status}'
    return '❌ No encontrado'


# === COLECCIÓN DE MÉTRICAS ===

def main():
    print(f"🌌 Vía Láctea — Generando snapshot para {TODAY}...")
    
    # --- Infraestructura ---
    infra = {
        'BACKBONE API': check_service('backbone-api'),
        'Caddy': check_service('caddy'),
        'PostgreSQL': get_uptime_docker('backbone-postgres'),
        'Redis': get_uptime_docker('backbone-redis'),
        'Meilisearch': get_uptime_docker('backbone-meilisearch'),
        'Prometheus': get_uptime_docker('hermes_prometheus'),
        'Grafana': get_uptime_docker('hermes_grafana'),
        'Open WebUI': get_uptime_docker('open-webui'),
        'MCPO GHL': get_uptime_docker('mcpo-ghl'),
    }
    
    # --- Health Check BACKBONE ---
    health_raw = run('curl -s --max-time 5 http://localhost:8005/health 2>/dev/null')
    health_status = '⚠️ No responde'
    health_detail = ''
    if health_raw and health_raw != '(timeout)':
        try:
            h = json.loads(health_raw)
            health_status = '✅ OK' if h.get('status') == 'ok' else f'⚠️ {h.get("status")}'
            health_detail = f'db={h.get("database")} meili={h.get("meilisearch")} redis={h.get("redis")} scraping={h.get("scraping")}'
        except json.JSONDecodeError:
            health_status = '⚠️ Respuesta inválida'
    
    # --- Puertos ---
    ports = {
        8005: 'BACKBONE API',
        5432: 'PostgreSQL',
        6379: 'Redis',
        7700: 'Meilisearch',
        9090: 'Prometheus',
        3000: 'Grafana',
    }
    port_status = {name: check_port(port) for port, name in ports.items()}
    
    # --- Proyectos count ---
    inventario_path = WORKSPACE / 'projects' / 'INVENTARIO-MAESTRO.md'
    if inventario_path.exists():
        content = inventario_path.read_text()
        en_creacion = len(re.findall(r'^|\|.*?\|.*?\|.*?\|.*?\|.*?\|', content, re.MULTILINE))
        total_productos = len(re.findall(r'^\|', content, re.MULTILINE)) - 5  # header lines
    else:
        total_productos = '?'
    
    # --- Documentos Vía Láctea ---
    via_lactea_files = [
        'BITACORA.md', 'CHANGELOG.md',
        'ADR/001-omega-bridge-meta-router.md',
        'ADR/002-fastapi-stack-backend.md',
        'ADR/003-pits-ghl-multi-tenancy.md',
        'docs/README.md', 'docs/GUIA-99.md', 'docs/GUIA-1.md', 'docs/MANIFIESTO.md',
    ]
    doc_sizes = {}
    total_doc_kb = 0
    for f in via_lactea_files:
        path = WORKSPACE / 'projects' / f
        if path.exists():
            size_kb = path.stat().st_size / 1024
            doc_sizes[f] = f'{size_kb:.0f} KB'
            total_doc_kb += size_kb
    
    # --- Último git log ---
    git_last = run('cd /home/polaris/workspace && git log -1 --format="%h %s (%ar)" 2>/dev/null')
    
    # --- Docker count ---
    docker_count = run('docker ps --format "{{.Names}}" 2>/dev/null | wc -l')
    
    # === GENERAR MARKDOWN ===
    
    md = f"""# 📊 STATUS Snapshot — {TODAY}

> ═══════════════════════════════════════════════════════════
> **Sistema Vía Láctea — Snapshot de Estado**
> **Generado:** {TODAY} {datetime.now(MEX_TZ).strftime('%H:%M')} UTC-6  
> **Por:** OmegaBridge (Hermes Agent) · Snapshot Automático  
> **Propósito:** Foto periódica del ecosistema — salud, métricas, cambios  
> ═══════════════════════════════════════════════════════════

---

## 🟢 Infraestructura — Salud General

| Sistema | Estado | Puerto |
|---------|--------|--------|
"""
    
    for name, status in infra.items():
        port = [str(p) for p, n in ports.items() if n == name]
        port_str = f':{port[0]}' if port else '—'
        md += f"| **{name}** | {status} | {port_str} |\n"
    
    md += f"""
### BACKBONE API Health
- **Estado:** {health_status}
- **Detalle:** {health_detail}

---

## 📊 Métricas Agregadas

| Métrica | Valor |
|---------|-------|
| Documentos Vía Láctea | {len(doc_sizes)} archivos · {total_doc_kb:.0f} KB |
| Contenedores Docker activos | {docker_count} |
| Último commit workspace | {git_last} |
| Fecha del snapshot | {TODAY} |

---

## 📦 Documentos Vía Láctea

| Documento | Tamaño |
|-----------|:------:|
"""
    
    for doc, size in doc_sizes.items():
        md += f"| `{doc}` | {size} |\n"
    
    md += f"""
---

## 📈 Cambios desde último snapshot

*Registrados automáticamente. Ver `CHANGELOG.md` y `BITACORA.md` para detalles.*

---

> *Snapshot generado automáticamente por el cron de Vía Láctea.*
"""
    
    # === ESCRIBIR ===
    OUTPUT_FILE.write_text(md)
    print(f"✅ Snapshot escrito: {OUTPUT_FILE} ({OUTPUT_FILE.stat().st_size / 1024:.0f} KB)")
    return 0

if __name__ == '__main__':
    sys.exit(main())
