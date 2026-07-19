#!/usr/bin/env python3
"""
PADIM Daily Monitor — Reporte diario de cambios en propiedades.
Se ejecuta cada mañana vía cron.
Reporta: cuántas propiedades cambiaron, ghost listings, nuevos listings.
"""
import subprocess, json
from datetime import datetime, timezone, timedelta

DB_USER = "backbone"
DB_NAME = "backbone"
NOW = datetime.now(timezone.utc)
YESTERDAY = NOW - timedelta(days=1)

def query(sql):
    r = subprocess.run(
        ["docker", "exec", "-i", "backbone-postgres", "psql", "-U", DB_USER, "-d", DB_NAME, "-t", "-A", "-F", "|"],
        input=sql, capture_output=True, text=True, timeout=30
    )
    return r.stdout.strip()

def main():
    print(f"📊 PADIM Daily Monitor — {NOW.strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    # 1. Total de propiedades
    total = query("SELECT COUNT(*) FROM properties;")
    print(f"\n📦 Propiedades totales: {total}")

    # 2. Propiedades scrapeadas hoy (nuevas o actualizadas)
    new_today = query(f"""
        SELECT COUNT(*) FROM properties 
        WHERE last_updated >= '{YESTERDAY.isoformat()}'
           OR created_at >= '{YESTERDAY.isoformat()}';
    """)
    print(f"🆕 Actualizadas hoy: {new_today}")

    # 3. Nuevos snapshots (cambios detectados)
    snaps_today = query(f"""
        SELECT COUNT(*) FROM property_snapshots 
        WHERE scraped_at >= '{YESTERDAY.isoformat()}';
    """)
    props_with_changes = query(f"""
        SELECT COUNT(DISTINCT property_id) FROM property_snapshots 
        WHERE scraped_at >= '{YESTERDAY.isoformat()}';
    """)
    print(f"📸 Snapshots nuevos: {snaps_today} (de {props_with_changes} propiedades)")

    # 4. Ghost listings (>30 días sin cambios)
    ghost = query("""
        SELECT COUNT(*) FROM (
            SELECT ps.property_id, MAX(ps.scraped_at) as last_seen
            FROM property_snapshots ps
            JOIN properties p ON p.id = ps.property_id
            WHERE p.quality_score > 0.3 AND p.price > 0
            GROUP BY ps.property_id
            HAVING EXTRACT(DAY FROM (NOW() - MAX(ps.scraped_at))) >= 30
        ) g;
    """)
    print(f"👻 Ghost listings (>30d): {ghost}")

    # 5. Precios que cambiaron
    price_changes = query(f"""
        SELECT COUNT(*) FROM property_snapshots ps
        WHERE ps.scraped_at >= '{YESTERDAY.isoformat()}'
          AND ps.content_hash != (
              SELECT content_hash FROM property_snapshots 
              WHERE property_id = ps.property_id AND scraped_at < ps.scraped_at
              ORDER BY scraped_at DESC LIMIT 1
          );
    """)
    print(f"💰 Precios cambiados: {price_changes}")

    # 6. Top 5 ghost listings por estado
    top_ghost = query("""
        SELECT p.state, COUNT(*) as ghost_count
        FROM (
            SELECT property_id, MAX(scraped_at) as scraped_at
            FROM property_snapshots GROUP BY property_id
        ) ps
        JOIN properties p ON p.id = ps.property_id
        WHERE EXTRACT(DAY FROM (NOW() - ps.scraped_at)) >= 30
          AND p.quality_score > 0.3
        GROUP BY p.state
        ORDER BY ghost_count DESC LIMIT 5
    """)
    print("\n🏛️ Ghosts por estado (top 5):")
    for line in top_ghost.split('\n'):
        if line.strip():
            parts = line.split('|')
            if len(parts) == 2:
                print(f"   {parts[0]}: {parts[1]}")

    # 7. Salud del scraping
    sources = query("""
        SELECT source, COUNT(*) as total,
               MAX(scraped_at)::DATE as last_seen
        FROM properties 
        GROUP BY source 
        ORDER BY total DESC
    """)
    print("\n🔍 Fuentes activas:")
    for line in sources.split('\n'):
        if line.strip():
            parts = line.split('|')
            if len(parts) >= 3:
                days_since = (NOW.date() - datetime.strptime(parts[2][:10], '%Y-%m-%d').date()).days if parts[2] else '?'
                print(f"   {parts[0]:<20} {parts[1]:>6} props  (último: {parts[2][:10] if parts[2] else 'N/A'}, {days_since}d atrás)")

    print(f"\n{'=' * 60}")
    print(f"✅ Reporte generado: {NOW.isoformat()}")

if __name__ == "__main__":
    main()