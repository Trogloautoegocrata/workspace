#!/usr/bin/env python3
"""
BACKBONE — Quality Trend Tracker
=================================
Guarda snapshots históricos de calidad para tracking de tendencias.
Genera reportes de tendencias semanales.

Uso:
  python3 quality_trends.py --record   # Guarda snapshot actual en histórico
  python3 quality_trends.py --report   # Genera reporte de tendencias
  python3 quality_trends.py --weekly    # Digest semanal
"""
import psycopg2
import json
import os
import sys
from datetime import datetime, timezone, timedelta

DB = {"host": "localhost", "port": 5432, "dbname": "backbone",
      "user": "backbone", "password": "backbone_dev_pass"}

TRENDS_FILE = "/home/polaris/workspace/data/quality-trends.jsonl"
CURRENT_SNAPSHOT = "/home/polaris/workspace/data/quality-snapshot.json"


def get_current_snapshot():
    """Obtiene snapshot actual de DB (reutiliza lógica de quality_report)."""
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()

    snapshot = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total": 0,
        "sources": {},
        "distribution": {},
        "freshness": {},
    }

    cur.execute("SELECT COUNT(*) FROM properties")
    snapshot["total"] = cur.fetchone()[0]

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
            GROUP BY
              CASE
                WHEN quality_score >= 0.7 THEN 'GOLD'
                WHEN quality_score >= 0.5 THEN 'SILVER'
                WHEN quality_score >= 0.3 THEN 'BRONZE'
                WHEN quality_score IS NULL THEN 'NULL'
                ELSE 'TRASH'
              END
        """)
    snapshot["distribution"] = dict(cur.fetchall())

    cur.execute("""
        SELECT source, COUNT(*),
          SUM(CASE WHEN quality_score < 0.3 THEN 1 ELSE 0 END) as trash,
          ROUND(AVG(quality_score)::numeric, 2) as avg
        FROM properties WHERE quality_score IS NOT NULL
        GROUP BY source ORDER BY COUNT(*) DESC
    """)
    for row in cur.fetchall():
        source, total, trash, avg = row
        snapshot["sources"][source] = {
            "total": total, "trash": trash,
            "usable_pct": round(100 * (total - trash) / total, 1) if total else 0,
            "avg_score": float(avg) if avg else 0,
        }

    cur.execute("""
        SELECT
          CASE
            WHEN scraped_at >= NOW() - interval '7 days' THEN 'fresh'
            WHEN scraped_at >= NOW() - interval '30 days' THEN 'stale'
            WHEN scraped_at < NOW() - interval '30 days' THEN 'old'
            ELSE 'unknown'
          END as freshness,
          COUNT(*)
        FROM properties
        GROUP BY
          CASE
            WHEN scraped_at >= NOW() - interval '7 days' THEN 'fresh'
            WHEN scraped_at >= NOW() - interval '30 days' THEN 'stale'
            WHEN scraped_at < NOW() - interval '30 days' THEN 'old'
            ELSE 'unknown'
          END
    """)
    snapshot["freshness"] = dict(cur.fetchall())

    cur.close()
    conn.close()
    return snapshot


def record_snapshot():
    """Guarda snapshot actual como una línea en el histórico."""
    snapshot = get_current_snapshot()
    os.makedirs(os.path.dirname(TRENDS_FILE), exist_ok=True)
    with open(TRENDS_FILE, "a") as f:
        f.write(json.dumps(snapshot, default=str) + "\n")
    print(f"✅ Snapshot registrado: {snapshot['total']} props, {snapshot['timestamp'][:19]}")
    return snapshot


def load_trends(days=None):
    """Carga snapshots históricos. Si days=N, solo últimos N días."""
    if not os.path.exists(TRENDS_FILE):
        return []
    now = datetime.now(timezone.utc)
    snapshots = []
    with open(TRENDS_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                snap = json.loads(line)
                snap_time = datetime.fromisoformat(snap["timestamp"])
                if days is None or (now - snap_time).days <= days:
                    snapshots.append(snap)
    return snapshots


def generate_trend_report(snapshots):
    """Genera reporte de tendencias a partir del histórico."""
    if len(snapshots) < 2:
        return "Se necesitan al menos 2 snapshots para detectar tendencias."

    first = snapshots[0]
    last = snapshots[-1]
    days_span = round((datetime.fromisoformat(last["timestamp"]) -
                       datetime.fromisoformat(first["timestamp"])).total_seconds() / 86400, 1)

    lines = []
    lines.append(f"# 📈 BACKBONE — Quality Trends ({days_span} días)")
    lines.append(f"**Período:** {first['timestamp'][:10]} → {last['timestamp'][:10]}")
    lines.append(f"**Snapshots:** {len(snapshots)}")
    lines.append("")

    # Tendencia de volumen total
    vol_start = first["total"]
    vol_end = last["total"]
    vol_change = round(100 * (vol_end - vol_start) / vol_start, 1) if vol_start else 0
    arrow = "📈" if vol_change > 0 else "📉"
    lines.append(f"## Volumen Total")
    lines.append(f"  {arrow} {vol_start:,} → {vol_end:,} ({'+' if vol_change > 0 else ''}{vol_change}%)")
    lines.append("")

    # Tendencia de TRASH
    lines.append(f"## TRASH")
    for snap in snapshots:
        date = snap["timestamp"][:10]
        trash = snap["distribution"].get("TRASH", 0)
        pct = round(100 * trash / snap["total"], 1)
        lines.append(f"  {date}: {trash:,} ({pct}%)")

    trash_start = first["distribution"].get("TRASH", 0)
    trash_end = last["distribution"].get("TRASH", 0)
    trash_change = trash_end - trash_start
    arrow = "⚠️" if trash_change > 0 else "✅"
    lines.append(f"  {arrow} Cambio: {'+' if trash_change > 0 else ''}{trash_change:,}")
    lines.append("")

    # Tendencia por fuente
    lines.append(f"## Por Fuente (usable%)")
    lines.append("")
    header = "| Fuente | " + " | ".join(s["timestamp"][5:10] for s in snapshots) + " |"
    sep = "|--------|" + "|".join(":-----:" for _ in snapshots) + "|"
    lines.append("")
    lines.append("")

    all_sources = set()
    for snap in snapshots:
        all_sources.update(snap["sources"].keys())

    for source in sorted(all_sources):
        row = f"| {source[:25]:25s} "
        for snap in snapshots:
            data = snap["sources"].get(source)
            if data:
                row += f"| {data['usable_pct']:>5.1f}% "
            else:
                row += "|   N/A "
        row += "|"
        lines.append("")
    lines.append("")

    # Freshness trend
    lines.append(f"## Freshness")
    for snap in snapshots:
        date = snap["timestamp"][:10]
        fresh = snap["freshness"].get("fresh", 0)
        stale = snap["freshness"].get("stale", 0)
        old = snap["freshness"].get("old", 0)
        lines.append(f"  {date}: fresh={fresh:,} stale={stale:,} old={old:,}")

    return "\n".join(lines)


def generate_weekly_digest():
    """Genera digest semanal de calidad."""
    snapshots = load_trends(days=7)
    if not snapshots:
        return "No hay datos de los últimos 7 días."

    # Reporte de tendencias
    trend = generate_trend_report(snapshots)
    return trend


def main():
    if "--record" in sys.argv:
        record_snapshot()
        return

    if "--weekly" in sys.argv:
        digest = generate_weekly_digest()
        # Guardar digest
        output = "/home/polaris/workspace/data/quality-weekly.md"
        os.makedirs(os.path.dirname(output), exist_ok=True)
        with open(output, "w") as f:
            f.write(digest)
        print(f"✅ Weekly digest: {output}")
        print(digest)
        return

    if "--report" in sys.argv:
        days = 7
        for arg in sys.argv:
            if arg.startswith("--days="):
                days = int(arg.split("=", 1)[1])
        snapshots = load_trends(days=days)
        if len(snapshots) < 2:
            print(f"⚠️ Solo {len(snapshots)} snapshot(s) en {days} días. Necesito al menos 2.")
            return
        report = generate_trend_report(snapshots)
        print(report)
        return

    # Default: record
    record_snapshot()


if __name__ == "__main__":
    main()