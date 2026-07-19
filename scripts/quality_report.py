#!/usr/bin/env python3
"""
BACKBONE — Data Quality Report Generator
=========================================
Genera un reporte de calidad de datos con:
- Distribución por fuente vs snapshot anterior
- Freshness metrics
- Alertas inteligentes (solo cuando algo cambia)

Uso:
  python3 quality_report.py                    # Reporte completo
  python3 quality_report.py --watchdog         # Solo alertas si hay cambios
  python3 quality_report.py --output report.md # Guardar a archivo

Forma parte del pipeline de scraping (Fase 3: Automatización).
"""
import psycopg2
import json
import os
import sys
from datetime import datetime, timezone

DB = {"host": "localhost", "port": 5432, "dbname": "backbone",
      "user": "backbone", "password": "backbone_dev_pass"}

SNAPSHOT_FILE = "/home/polaris/workspace/data/quality-snapshot.json"
REPORT_FILE = "/home/polaris/workspace/data/quality-report.md"

# Umbrales para alertas
ALERT_THRESHOLDS = {
    "source_usable_drop_pct": 5.0,    # Caída >5% en tasa usable de una fuente
    "trash_spike_pct": 10.0,           # Aumento >10% de TRASH
    "freshness_crisis_days": 7,        # Si scraping no corre en 7+ días
    "total_volume_drop_pct": 20.0,     # Caída >20% en volumen total
}


def get_quality_snapshot():
    """Obtiene snapshot actual de calidad desde DB."""
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()

    snapshot = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_properties": 0,
        "by_source": {},
        "distribution": {},
        "freshness": {},
        "metrics": {},
    }

    # Total
    cur.execute("SELECT COUNT(*) FROM properties")
    snapshot["total_properties"] = cur.fetchone()[0]

    # Distribución global
    cur.execute("""
        SELECT
          CASE
            WHEN quality_score >= 0.7 THEN 'GOLD'
            WHEN quality_score >= 0.5 THEN 'SILVER'
            WHEN quality_score >= 0.3 THEN 'BRONZE'
            WHEN quality_score IS NULL THEN 'NULL'
            ELSE 'TRASH'
          END as grade,
          COUNT(*)
        FROM properties
        GROUP BY grade
    """)
    snapshot["distribution"] = dict(cur.fetchall())

    # Por fuente
    cur.execute("""
        SELECT source,
          COUNT(*) as total,
          SUM(CASE WHEN quality_score >= 0.5 THEN 1 ELSE 0 END) as silver_plus,
          SUM(CASE WHEN quality_score >= 0.3 AND quality_score < 0.5 THEN 1 ELSE 0 END) as bronze,
          SUM(CASE WHEN quality_score < 0.3 THEN 1 ELSE 0 END) as trash,
          ROUND(AVG(quality_score)::numeric, 2) as avg_score
        FROM properties
        WHERE quality_score IS NOT NULL
        GROUP BY source
        ORDER BY total DESC
    """)
    for row in cur.fetchall():
        source, total, silver, bronze, trash, avg = row
        usable = total - trash
        snapshot["by_source"][source] = {
            "total": total,
            "silver_plus": silver,
            "bronze": bronze,
            "trash": trash,
            "usable": usable,
            "usable_pct": round(100 * usable / total, 1) if total > 0 else 0,
            "avg_score": float(avg) if avg else 0,
        }

    # Freshness
    cur.execute("""
        SELECT
          CASE
            WHEN scraped_at >= NOW() - interval '7 days' THEN 'fresh'
            WHEN scraped_at >= NOW() - interval '30 days' THEN 'stale'
            WHEN scraped_at >= NOW() - interval '90 days' THEN 'old'
            WHEN scraped_at < NOW() - interval '90 days' THEN 'ancient'
            ELSE 'unknown'
          END as freshness,
          COUNT(*)
        FROM properties
        GROUP BY freshness
    """)
    snapshot["freshness"] = dict(cur.fetchall())

    # Métricas adicionales
    cur.execute("SELECT COUNT(*) FROM properties WHERE quality_score IS NULL")
    null_score = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM properties WHERE price IS NULL OR price = 0")
    no_price = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM properties WHERE lat IS NULL OR lng IS NULL")
    no_coords = cur.fetchone()[0]

    cur.execute("SELECT MAX(scraped_at) FROM properties")
    last_scrape = cur.fetchone()[0]

    snapshot["metrics"] = {
        "null_score": null_score,
        "no_price": no_price,
        "no_coords": no_coords,
        "last_scrape": last_scrape.isoformat() if last_scrape else None,
        "days_since_last_scrape": (datetime.now(timezone.utc) - last_scrape).days if last_scrape else None,
    }

    cur.close()
    conn.close()
    return snapshot


def load_previous_snapshot():
    """Carga el snapshot anterior."""
    if not os.path.exists(SNAPSHOT_FILE):
        return None
    try:
        with open(SNAPSHOT_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def save_snapshot(snapshot):
    """Guarda el snapshot actual."""
    os.makedirs(os.path.dirname(SNAPSHOT_FILE), exist_ok=True)
    with open(SNAPSHOT_FILE, "w") as f:
        json.dump(snapshot, f, indent=2, default=str)


def detect_alerts(current, previous):
    """Detecta cambios significativos entre snapshots."""
    alerts = []

    if not previous:
        return alerts  # Primer snapshot, no hay alertas

    # 1. Caída en tasa usable por fuente
    for source, data in current["by_source"].items():
        if source in previous.get("by_source", {}):
            prev = previous["by_source"][source]
            change = data["usable_pct"] - prev["usable_pct"]
            if change < -ALERT_THRESHOLDS["source_usable_drop_pct"]:
                alerts.append({
                    "type": "source_quality_drop",
                    "severity": "warning",
                    "message": f"📉 {source}: tasa usable bajó {abs(change):.1f}% "
                              f"({prev['usable_pct']}% → {data['usable_pct']}%)",
                    "source": source,
                    "change_pct": round(change, 1),
                })

    # 2. Aumento de TRASH global
    curr_trash = current["distribution"].get("TRASH", 0)
    prev_trash = previous["distribution"].get("TRASH", 0) if previous else 0
    if prev_trash > 0:
        trash_change = round(100 * (curr_trash - prev_trash) / prev_trash, 1)
        if trash_change > ALERT_THRESHOLDS["trash_spike_pct"]:
            alerts.append({
                "type": "trash_spike",
                "severity": "critical",
                "message": f"🚨 TRASH aumentó {trash_change}% "
                          f"({prev_trash} → {curr_trash})",
                "change_pct": trash_change,
            })

    # 3. Freshness crisis
    days_since = current["metrics"].get("days_since_last_scrape")
    if days_since and days_since > ALERT_THRESHOLDS["freshness_crisis_days"]:
        alerts.append({
            "type": "freshness_crisis",
            "severity": "critical",
            "message": f"⏰ Sin scraping fresco en {days_since} días",
            "days": days_since,
        })

    # 4. Cambio de volumen total
    curr_total = current["total_properties"]
    prev_total = previous["total_properties"]
    if prev_total > 0:
        vol_change = round(100 * (curr_total - prev_total) / prev_total, 1)
        if abs(vol_change) > ALERT_THRESHOLDS["total_volume_drop_pct"]:
            alerts.append({
                "type": "volume_anomaly",
                "severity": "warning",
                "message": f"📊 Volumen cambió {vol_change}% "
                          f"({prev_total} → {curr_total})",
                "change_pct": vol_change,
            })

    return alerts


def generate_report(current, previous, alerts):
    """Genera reporte markdown."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = []

    lines.append(f"# 📊 BACKBONE — Data Quality Report")
    lines.append(f"**Generado:** {now}")
    lines.append(f"**Total propiedades:** {current['total_properties']:,}")
    lines.append("")

    # Alertas
    if alerts:
        lines.append("## 🚨 Alertas Detectadas")
        for a in alerts:
            icon = "🔴" if a["severity"] == "critical" else "🟡"
            lines.append(f"- {icon} {a['message']}")
        lines.append("")

    # Distribución global
    lines.append("## 📈 Distribución Global")
    total = current["total_properties"]
    for grade in ["GOLD", "SILVER", "BRONZE", "TRASH"]:
        count = current["distribution"].get(grade, 0)
        pct = round(100 * count / total, 1) if total > 0 else 0
        prev_count = previous["distribution"].get(grade, 0) if previous else 0
        prev_pct = round(100 * prev_count / previous["total_properties"], 1) if previous and previous["total_properties"] > 0 else 0
        change = pct - prev_pct
        arrow = f" ({'+' if change > 0 else ''}{change:.1f}%)" if previous else ""
        lines.append(f"  {grade}: {count:>7,} ({pct:>5.1f}%){arrow}")
    lines.append("")

    # Por fuente
    lines.append("## 🏢 Por Fuente")
    lines.append("")
    lines.append("| Fuente | Total | GOLD+ | BRONZE | TRASH | Usable% | Score |")
    lines.append("|--------|:----:|:-----:|:------:|:----:|:------:|:-----:|")
    for source, data in sorted(current["by_source"].items(),
                                key=lambda x: x[1]["total"], reverse=True):
        lines.append(
            f"| {source[:25]:25s} | {data['total']:>6,} | "
            f"{data['silver_plus']:>5,} | {data['bronze']:>5,} | "
            f"{data['trash']:>5,} | {data['usable_pct']:>5.1f}% | "
            f"{data['avg_score']:.2f} |"
        )
    lines.append("")

    # Freshness
    lines.append("## ⏱️ Freshness")
    for level in ["fresh", "stale", "old", "ancient", "unknown"]:
        count = current["freshness"].get(level, 0)
        pct = round(100 * count / total, 1) if total > 0 else 0
        lines.append(f"  {level}: {count:>7,} ({pct:>5.1f}%)")
    lines.append("")

    # Métricas
    lines.append("## ⚙️ Métricas")
    lines.append(f"  Quality Score NULL: {current['metrics']['null_score']:,}")
    lines.append(f"  Sin precio: {current['metrics']['no_price']:,}")
    lines.append(f"  Sin coordenadas: {current['metrics']['no_coords']:,}")
    if current["metrics"]["days_since_last_scrape"] is not None:
        lines.append(f"  Último scrape: hace {current['metrics']['days_since_last_scrape']} días")
    lines.append("")

    # Resumen de cambios vs anterior
    if previous:
        lines.append("## 🔄 Cambios desde último reporte")
        for source, data in current["by_source"].items():
            if source in previous.get("by_source", {}):
                prev = previous["by_source"][source]
                usable_change = data["usable_pct"] - prev["usable_pct"]
                if abs(usable_change) > 1.0:
                    arrow = "📈" if usable_change > 0 else "📉"
                    lines.append(f"  {arrow} {source}: {prev['usable_pct']}% → {data['usable_pct']}% "
                                f"usable ({'+' if usable_change > 0 else ''}{usable_change:.1f}%)")

    return "\n".join(lines)


def main():
    is_watchdog = "--watchdog" in sys.argv
    output_file = None
    for i, arg in enumerate(sys.argv):
        if arg.startswith("--output="):
            output_file = arg.split("=", 1)[1]
        elif arg == "--output" and i + 1 < len(sys.argv):
            output_file = sys.argv[i + 1]

    # Obtener snapshot actual
    current = get_quality_snapshot()

    # Cargar anterior
    previous = load_previous_snapshot()

    # Detectar alertas
    alerts = detect_alerts(current, previous)

    # Modo watchdog: solo reportar si hay alertas
    if is_watchdog:
        if alerts:
            print(f"# 🚨 BACKBONE Quality Watchdog — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            for a in alerts:
                icon = "🔴" if a["severity"] == "critical" else "🟡"
                print(f"{icon} {a['message']}")
        # Guardar snapshot igualmente para tracking
        save_snapshot(current)
        return

    # Generar reporte
    report = generate_report(current, previous, alerts)

    # Guardar snapshot
    save_snapshot(current)

    # Output
    if output_file:
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, "w") as f:
            f.write(report)
        print(f"✅ Reporte guardado: {output_file}")
    else:
        print(report)


if __name__ == "__main__":
    main()