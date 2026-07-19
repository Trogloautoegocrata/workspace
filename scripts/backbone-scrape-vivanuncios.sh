#!/usr/bin/env bash
# backbone-scrape-vivanuncios.sh
# Scraper Vivanuncios vía curl_cffi — 6 páginas cada corrida (~180 props)
# Ejecuta desde el venv de BACKBONE
set -e
cd /home/polaris/workspace/projects/BACKBONE
source .venv/bin/activate
python3 << 'PYEOF'
import asyncio, json, sys
from datetime import datetime
from src.scrapers.connectors.vivanuncios_curl import VivanunciosCurlConnector
from src.api.database import SessionLocal
from src.api.models import Property
from sqlalchemy import select

async def save_to_db(db, prop):
    """Guarda en PostgreSQL + Meilisearch si existe el índice"""
    try:
        from sqlalchemy import select
        existing = await db.execute(
            select(Property).where(
                Property.source == prop["source"],
                Property.source_id == prop["source_id"]
            )
        )
        existing_prop = existing.scalar_one_or_none()
        if existing_prop:
            for k, v in prop.items():
                if v is not None and k not in ('source', 'source_id', 'created_at'):
                    setattr(existing_prop, k, v)
            existing_prop.last_updated = datetime.utcnow()
        else:
            db.add(Property(**prop))
        await db.commit()
        return True
    except Exception as e:
        await db.rollback()
        print(f"  ⚠️ Error DB: {e}", file=sys.stderr)
        return False

async def main():
    print(f"[{datetime.now().isoformat()}] Iniciando scrape Vivanuncios...")
    conn = VivanunciosCurlConnector()
    async with conn:
        result = await conn.run_full_scrape(max_pages=6)
    
    props = result.data.get("properties", []) if result.success else []
    print(f"📊 Obtenidas: {len(props)} propiedades en {result.duration_ms/1000:.1f}s")
    
    # Guardar en DB
    saved = 0
    async with SessionLocal() as db:
        for prop in props:
            try:
                from sqlalchemy import select
                existing = await db.execute(
                    select(Property).where(
                        Property.source == prop["source"],
                        Property.source_id == prop["source_id"]
                    )
                )
                if existing.scalar_one_or_none():
                    continue  # ya existe
                db.add(Property(**prop))
                saved += 1
            except Exception as e:
                print(f"  ⚠️ Error: {e}")
        await db.commit()
    
    print(f"💾 Guardadas nuevas: {saved}")
    print(f"[{datetime.now().isoformat()}] Scrape completado ✅")

asyncio.run(main())
PYEOF