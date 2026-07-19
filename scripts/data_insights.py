#!/usr/bin/env python3
"""
BACKBONE — Data Insights Generator (Opción A, $0)
==================================================
Lee los trends históricos de calidad y genera insights automáticos
sin gastar tokens de IA.

Insights que genera:
- Fuentes que mejoran/empeoran
- Tendencias de freshness
- Anomalías de volumen
- Datos útiles para blog (precios, tendencias por zona)
- Recomendaciones de scraping

Uso:
  python3 data_insights.py                    # Insights generales
  python3 data_insights.py --blog             # Insights para artículos de blog
  python3 data_insights.py --recomendar       # Solo recomendaciones de scraping
"""
import json
import os
import sys
from datetime import datetime, timezone
from collections import defaultdict

TRENDS_FILE = "/home/polaris/workspace/data/quality-trends.jsonl"
BLOG_FILE = "/home/polaris/workspace/data/blog-insights.md"
RECOMMEND_FILE = "/home/polaris/workspace/data/scrape-recommendations.md"


def load_trends(days=14):
    """Carga snapshots históricos de los últimos N días."""
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
                if (now - snap_time).days <= days:
                    snapshots.append(snap)
    return snapshots


def generate_insights(snapshots):
    """Genera insights de datos sin usar IA."""
    if len(snapshots) < 2:
        return ["Se necesitan al menos 2 snapshots para generar insights. Los datos se acumulan con cada ciclo del pipeline."]

    insights = []
    first = snapshots[0]
    last = snapshots[-1]
    days = round((datetime.fromisoformat(last["timestamp"]) -
                  datetime.fromisoformat(first["timestamp"])).total_seconds() / 86400, 1)

    # 1. Volumen total
    vol_change = last["total"] - first["total"]
    if vol_change > 0:
        insights.append(f"📈 Volumen: +{vol_change} propiedades en {days} días ({last['total']:,} total)")
    elif vol_change < 0:
        insights.append(f"📉 Volumen: -{abs(vol_change)} propiedades en {days} días")

    # 2. TRASH tracking
    trash_first = first["distribution"].get("TRASH", 0)
    trash_last = last["distribution"].get("TRASH", 0)
    trash_change = trash_last - trash_first
    if trash_change > 0:
        pct_first = round(100 * trash_first / first["total"], 1)
        pct_last = round(100 * trash_last / last["total"], 1)
        insights.append(f"⚠️ TRASH: +{trash_change} ({pct_first}% → {pct_last}%) — revisar fuentes en declive")
    elif trash_change < 0:
        insights.append(f"✅ TRASH: -{abs(trash_change)} — la limpieza está funcionando")

    # 3. Fuentes que mejoran/empeoran
    for source in sorted(last.get("sources", {}).keys()):
        first_data = first["sources"].get(source)
        last_data = last["sources"].get(source)
        if not first_data or not last_data:
            continue
        usable_change = last_data["usable_pct"] - first_data["usable_pct"]
        if abs(usable_change) > 2.0:
            direction = "📈 mejora" if usable_change > 0 else "📉 empeora"
            insights.append(f"{direction}: {source} — usable {first_data['usable_pct']}% → {last_data['usable_pct']}%")

    # 4. Freshness
    fresh_first = first["freshness"].get("fresh", 0)
    fresh_last = last["freshness"].get("fresh", 0)
    fresh_change = fresh_last - fresh_first
    if fresh_change > 0:
        insights.append(f"🆕 Freshness: +{fresh_change} props frescas en {days} días")
    elif fresh_change < 0 and days > 1:
        insights.append(f"⏰ Freshness: -{abs(fresh_change)} props frescas — scraping podría estar cayendo")

    # 5. Scoring promedio
    scores = [(s, d["avg_score"]) for s, d in last["sources"].items() if d.get("avg_score")]
    if scores:
        best = max(scores, key=lambda x: x[1])
        worst = min(scores, key=lambda x: x[1])
        insights.append(f"🏆 Mejor fuente: {best[0]} (score {best[1]})")
        insights.append(f"🔻 Peor fuente: {worst[0]} (score {worst[1]})")

    return insights


def generate_blog_insights(snapshots):
    """Genera insights específicos para contenido de blog."""
    if not snapshots:
        return ["No hay datos aún. Los insights de blog estarán disponibles cuando se acumulen tendencias."]

    last = snapshots[-1]
    lines = []

    lines.append("# 📝 Blog Insights — Datos BACKBONE")
    lines.append(f"**Generado:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    # Insight 1: Distribución del mercado por fuente
    lines.append("## 🏠 ¿De dónde vienen los datos?")
    total = last["total"]
    for source, data in sorted(last["sources"].items(),
                                key=lambda x: x[1]["total"], reverse=True):
        pct = round(100 * data["total"] / total, 1) if total else 0
        usable = data["usable_pct"]
        lines.append(f"- **{source}**: {data['total']:,} props ({pct}% del total, {usable}% usable)")
    lines.append("")

    # Insight 2: Calidad del mercado
    trash_pct = round(100 * last["distribution"].get("TRASH", 0) / total, 1) if total else 0
    lines.append("## 📊 Salud del mercado inmobiliario")
    lines.append(f"- **{total:,}** propiedades analizadas en BACKBONE")
    lines.append(f"- **{trash_pct}%** son datos no confiables (ghost listings, stale)")
    lines.append(f"- **{round(100 - trash_pct, 1)}%** son datos utilizables para análisis de mercado")
    lines.append("")

    # Insight 3: Freshness
    fresh = last["freshness"].get("fresh", 0)
    stale = last["freshness"].get("stale", 0)
    ancient = last["freshness"].get("ancient", 0) + last["freshness"].get("old", 0)
    lines.append("## ⏱️ Actualización de datos")
    lines.append(f"- **{fresh:,}** propiedades actualizadas en la última semana")
    lines.append(f"- **{stale:,}** propiedades con datos de 1-4 semanas")
    lines.append(f"- **{ancient:,}** propiedades con datos de más de 1 mes")
    lines.append("")

    return "\n".join(lines)


def generate_recommendations(snapshots):
    """Genera recomendaciones de scraping basadas en calidad."""
    if len(snapshots) < 2:
        return ["No hay suficientes datos históricos para recomendaciones."]

    first = snapshots[0]
    last = snapshots[-1]
    recs = []

    for source in sorted(last.get("sources", {}).keys()):
        first_data = first["sources"].get(source)
        last_data = last["sources"].get(source)
        if not first_data or not last_data:
            continue

        # Si la fuente tiene alta tasa usable pero bajo volumen fresco
        if last_data["usable_pct"] > 80 and last_data["total"] > 100:
            # Verificar si está en decline
            if first_data["usable_pct"] - last_data["usable_pct"] > 3:
                recs.append(f"📋 **{source}**: Calidad alta pero DECLINANDO ({first_data['usable_pct']}% → {last_data['usable_pct']}%). Revisar scraping.")

        # Si la fuente tiene mucho TRASH
        trash_pct = round(100 * last_data.get("trash", 0) / last_data["total"], 1) if last_data["total"] else 0
        if trash_pct > 50 and last_data["total"] > 100:
            recs.append(f"🗑️ **{source}**: {trash_pct}% TRASH. Considerar depriorizar o limpiar.")

        # Si la fuente tiene muy pocos datos
        if last_data["total"] < 50:
            recs.append(f"🔍 **{source}**: Solo {last_data['total']} props. Vale la pena?")

    if not recs:
        recs.append("✅ Sin recomendaciones. Todas las fuentes estables.")

    return recs


def main():
    snapshots = load_trends(days=14)

    if "--blog" in sys.argv:
        blog = generate_blog_insights(snapshots)
        os.makedirs(os.path.dirname(BLOG_FILE), exist_ok=True)
        with open(BLOG_FILE, "w") as f:
            f.write(blog)
        print(blog)
        print(f"\n✅ Blog insights guardados: {BLOG_FILE}")
        return

    if "--recomendar" in sys.argv:
        recs = generate_recommendations(snapshots)
        print("# 🎯 Recomendaciones de Scraping")
        print()
        for r in recs:
            print(r)
        return

    # Default: insights generales
    insights = generate_insights(snapshots)
    print("# 💡 BACKBONE — Data Insights")
    print(f"**Snapshots analizados:** {len(snapshots)}")
    print()
    for i in insights:
        print(i)

    # Recomendaciones
    print()
    print("## 🎯 Recomendaciones")
    for r in generate_recommendations(snapshots):
        print(r)


if __name__ == "__main__":
    main()