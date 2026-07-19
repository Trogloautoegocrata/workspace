#!/usr/bin/env bash
# backbone-scrape-pipeline.sh v3.1 — Con History Layer + ghost detection + Inmuebles24
set -e

echo "⏰ [$(date -u +%Y-%m-%dT%H:%M:%SZ)] Iniciando pipeline BACKBONE v3.1..."

# Paso 1: Vivanuncios (curl_cffi, $0, ~11s/página)
echo "🔍 [STEP 1/6] Scraping Vivanuncios..."
cd /home/polaris/workspace/projects/BACKBONE
source .venv/bin/activate
python3 scripts/daily_vivanuncios_scrape.py 2>&1

# Paso 2: Doorvel Sitemap (httpx, $0, ~32K props)
echo "🔍 [STEP 2/6] Scraping Doorvel sitemap..."
cd /home/polaris/workspace
python3 scrapers/doorvel_sitemap_scraper.py --limit 100 --db --output /tmp/doorvel_latest.json 2>&1 || echo "  ⚠️ Doorvel sitemap falló (no crítica)"

# Paso 3: Inmuebles24 via ScrapingBee (~$0.01/request)
echo "🔍 [STEP 3/6] Scraping Inmuebles24 (ScrapingBee)..."
cd /home/polaris/workspace/projects/BACKBONE
source .venv/bin/activate
python3 -c "
from src.scrapers.connectors.inmuebles24_scrapingbee import Inmuebles24ScrapingBeeConnector
import asyncio
async def run():
    async with Inmuebles24ScrapingBeeConnector() as conn:
        result = await conn.run_full_scrape(max_pages=3)
        props = result.data.get('properties', [])
        print(f'  Inmuebles24: {len(props)} props en {result.duration_ms/1000:.1f}s')
asyncio.run(run())
" 2>&1 || echo "  ⚠️ Inmuebles24 falló (ScrapingBee créditos?)"

# Paso 4: Plalla Riviera Maya (JSON-LD, $0)
echo "🔍 [STEP 4/6] Scraping Plalla (Riviera Maya)..."
python3 /home/polaris/workspace/scrapers/plalla_detail_scraper.py --output /tmp/plalla_latest.json 2>&1 || echo "  ⚠️ Plalla falló (no crítica)"

# Paso 5: Calidad — evaluar propiedades nuevas
echo "🔬 [STEP 5/6] Evaluación de calidad..."
python3 /home/polaris/workspace/scrapers/quality_cron.py 2>&1

# Paso 6: Indexar a Meilisearch
echo "🔎 [STEP 6/6] Indexando DB → Meilisearch..."
python3 /home/polaris/workspace/projects/BACKBONE/scripts/index_meilisearch.py 2>&1 || echo "  ⚠️ Indexación falló"

# Reporte de calidad
python3 /home/polaris/workspace/scripts/quality_report.py --output /home/polaris/workspace/data/quality-report.md 2>&1 || echo "  ⚠️ Reporte falló"
python3 /home/polaris/workspace/scripts/quality_report.py --watchdog 2>&1
python3 /home/polaris/workspace/scripts/quality_trends.py --record 2>&1 || echo "  ⚠️ Trends falló"
python3 /home/polaris/workspace/scripts/data_insights.py 2>&1 || echo "  ⚠️ Insights falló"

echo "✅ [$(date -u +%Y-%m-%dT%H:%M:%SZ)] Pipeline v3.1 completado"
echo "📌 Nota: MLS, Propiedades.com y EasyBroker son seeds sintéticos (sin scraper real)"