#!/usr/bin/env python3
"""
BACKBONE — Indexar PostgreSQL → Meilisearch.
Crea índice 'properties' con filtros facetados, replica todas las props activas.
Uso: python3 scripts/backbone-index-meilisearch.py
"""
import asyncio, json, sys
from datetime import datetime

import httpx
import asyncpg

DB_DSN = "postgresql://backbone:backbone_dev_pass@localhost:5432/backbone"
MEILI_URL = "http://localhost:7700"
MEILI_KEY = "backbone_master_key_dev"

# Schema de columnas que pasan a Meilisearch (con casteo a texto para tipos no-JSON)
COLUMNAS = [
    "id::text", "source", "source_id", "source_url", "title", "description",
    "property_type", "business_type", "status",
    "price::text", "currency", "price_m2::text",
    "m2_constructed::text", "m2_land::text",
    "bedrooms", "bathrooms::text", "parking", "floors", "antiquity",
    "address", "colony", "municipality", "state", "country",
    "lat::text", "lng::text", "postal_code",
    "features::text", "amenities::text", "condition",
    "images::text",
    "agent_name", "agent_agency", "agent_phone",
    "scraped_at::text", "last_updated::text", "created_at::text",
]

async def get_meili_key():
    return "backbone_master_key_dev"

async def main():
    start = datetime.now()
    print(f"[{start.isoformat()}] 🚀 Indexando PostgreSQL → Meilisearch...")
    
    api_key = await get_meili_key()
    h = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    h["Content-Type"] = "application/json"
    
    pg = await asyncpg.connect(DB_DSN)
    
    try:
        # Contar total
        total = await pg.fetchval(
            "SELECT count(*) FROM properties WHERE is_deleted = false AND is_duplicate = false"
        )
        print(f"  📦 Props en PostgreSQL: {total:,}")
        
        # Crear/limpiar índice
        cols = ", ".join(COLUMNAS)
        
        async with httpx.AsyncClient(timeout=60.0) as http:
            # Eliminar índice si existe
            await http.delete(f"{MEILI_URL}/indexes/properties", headers=h)
            
            # Crear índice
            r = await http.post(f"{MEILI_URL}/indexes", headers=h, json={
                "uid": "properties", "primaryKey": "id"
            })
            print(f"  📁 Índice creado: HTTP {r.status_code}")
            
            # Settings con filtros facetados
            r = await http.patch(f"{MEILI_URL}/indexes/properties/settings", headers=h, json={
                "searchableAttributes": [
                    "title", "description", "colony", "municipality", "state",
                    "agent_name", "agent_agency", "address"
                ],
                "filterableAttributes": [
                    "source", "property_type", "business_type", "status",
                    "colony", "municipality", "state",
                    "price", "bedrooms", "bathrooms", "m2_constructed",
                    "price_m2", "antiquity"
                ],
                "sortableAttributes": ["price", "m2_constructed", "bedrooms", "created_at", "last_updated"],
            })
            print(f"  ⚙️  Settings: HTTP {r.status_code}")
            
            # Loop de batches
            BATCH = 500
            offset = 0
            indexed = 0
            
            while offset < total:
                rows = await pg.fetch(f"""
                    SELECT {cols} FROM properties 
                    WHERE is_deleted = false AND is_duplicate = false
                    ORDER BY created_at LIMIT $1 OFFSET $2
                """, BATCH, offset)
                
                if not rows:
                    break
                
                # Convertir rows a dicts, parsear tipos numéricos
                batch = []
                for row in rows:
                    d = dict(row)
                    # Limpiar: price y numéricos a float, json strings a objetos
                    for k in ["price", "price_m2", "m2_constructed", "m2_land", "lat", "lng"]:
                        if d.get(k) is not None:
                            try:
                                d[k] = float(d[k])
                            except (ValueError, TypeError):
                                d[k] = None
                    for k in ["bedrooms", "parking", "floors", "antiquity"]:
                        if d.get(k) is not None:
                            try:
                                d[k] = int(d[k])
                            except (ValueError, TypeError):
                                d[k] = None
                    # Parsear JSON strings a objetos
                    for k in ["features", "amenities", "images"]:
                        if d.get(k) and isinstance(d[k], str):
                            try:
                                d[k] = json.loads(d[k])
                            except json.JSONDecodeError:
                                d[k] = []
                    batch.append(d)
                
                r = await http.post(
                    f"{MEILI_URL}/indexes/properties/documents",
                    headers=h, json=batch
                )
                
                if r.status_code in (200, 202):
                    indexed += len(batch)
                    elapsed = (datetime.now() - start).total_seconds()
                    rate = indexed / elapsed if elapsed > 0 else 0
                    print(f"  ✔ {indexed:>6,}/{total:,} docs ({rate:.0f} docs/s)          ", end="\r")
                else:
                    print(f"\n  ❌ HTTP {r.status_code} en offset {offset}: {r.text[:200]}")
                
                offset += BATCH
            
            elapsed = (datetime.now() - start).total_seconds()
            print(f"\n  ─────────────────────────────────────")
            print(f"  ✅ {indexed:,} docs indexados en {elapsed:.1f}s")
            
            # Verificar
            r = await http.get(f"{MEILI_URL}/indexes/properties", headers=h)
            if r.status_code == 200:
                info = r.json()
                print(f"  📊 Índice: {info['uid']} — {info.get('numberOfDocuments',0):,} docs")
            
            # Prueba de búsqueda
            r = await http.post(f"{MEILI_URL}/indexes/properties/search", headers=h, json={
                "q": "departamento",
                "limit": 3,
                "facets": ["property_type", "business_type", "state"]
            })
            if r.status_code == 200:
                sr = r.json()
                print(f"  🔍 Búsqueda test: {sr.get('estimatedTotalHits',0):,} resultados para 'departamento'")
                print(f"     Facetas: {list(sr.get('facetDistribution',{}).keys())}")
    
    finally:
        await pg.close()

if __name__ == "__main__":
    asyncio.run(main())
