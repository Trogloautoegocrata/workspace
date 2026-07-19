#!/usr/bin/env python3
"""
SISTEMA DE CALIDAD DE CONTENIDO — Content Quality Engine
=========================================================
Se sienta entre los pipelines de generación y Pulsar.
Cada draft generado pasa por aquí antes de llegar a revisión humana.

Flujo:
  Pipeline genera draft (blog, email, ad, landing)
    → Quality Engine lo cuestiona y mejora
      → Genera reporte de calidad con score
        → Si score > umbral: envía a Pulsar como pending_review
        → Si score < umbral: devuelve a pipeline con recomendaciones

Qué revisa:
  1. 📝 Ortografía y gramática (sin depender de API externa)
  2. 🎯 Tono de voz y consistencia de marca
  3. 🔗 Claims y datos: verifica que las afirmaciones tengan respaldo
  4. 📏 Estructura y formato (scannability, heading hierarchy)
  5. 📊 SEO y palabras clave
  6. 🎨 Calidad general y valor para el lector
  7. 🚩 Señales de alerta (info falsa, promesas exageradas)
"""

import argparse
import json
import os
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

BASE_DIR = Path("/home/polaris/workspace")
PULSAR_DB = BASE_DIR / "pulsar" / "pulsar.db"

# ─── Puntuaciones y umbrales ──────────────────────────────────────────────
SCORE_WEIGHTS = {
    "ortografia": 0.15,
    "tono_voz": 0.20,
    "claims": 0.20,
    "estructura": 0.15,
    "seo": 0.10,
    "calidad_general": 0.20,
}

UMBRAL_APROBACION = 75  # Score mínimo para enviar a revisión humana
UMBRAL_CRITICO = 40     # Score bajo el cual se devuelve al pipeline con correcciones

# Palabras y frases que indican claims sin respaldo
CLAIMS_SIN_RESPALDO = [
    r"somos los mejores",
    r"el mejor [^.]+ del mercado",
    r"líder(es)? (absoluto|indiscutible|mundial)",
    r"número uno",
    r"revolucionar(á)?",
    r"la solución definitiva",
    r"100% (garantizado|efectivo|seguro)",
    r"resultados (garantizados|asegurados)",
    r"sin riesgo",
]

# Palabras que indican promesas exageradas
PROMESAS_EXAGERADAS = [
    r"gana dinero (sin esfuerzo|fácilmente|durmiendo)",
    r"hágase rico",
    r"resultados (instantáneos|inmediatos|milagrosos)",
    r"en solo [0-9]+ (días|horas|minutos)",
]

# ─── Check: Ortografía y Gramática ────────────────────────────────────────
def check_ortografia(text: str) -> Tuple[float, List[str]]:
    """Revisa ortografía y gramática básica sin API externa."""
    issues = []
    score = 100
    
    # Palabras comúnmente mal escritas en español inmobiliario
    common_errors = {
        r"\bhiva\b": "Hola (¿quizás querías decir 'viva'?)",
        r"\bhaiga\b": "haya",
        r"\bhaber si\b": "a ver si",
        r"\bhavia\b": "había",
        r"\baya\b": "haya (del verbo haber)",
        r"\bdeveria\b": "debería",
        r"\bnesecito\b": "necesito",
        r"\bgrasias\b": "gracias",
        r"\bporfavor\b": "por favor",
        r"\bsobre todo\b(?=\s+\w)": "sobre todo (contexto: principalmente)",
        r"\bmas sin embargo\b": "más sin embargo → no obstante / sin embargo",
    }
    
    for pattern, suggestion in common_errors.items():
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            issues.append(f"✏️ Posible error: '{pattern.strip('\\b')}' → {suggestion}")
            score -= 5 * len(matches)
    
    # Revisar signos de puntuación básicos
    sentences = re.split(r'[.!?]+', text)
    long_sentences = [s for s in sentences if len(s.split()) > 40]
    if long_sentences:
        issues.append(f"📏 {len(long_sentences)} oración(es) muy larga(s) (>40 palabras). Considera dividirlas.")
        score -= 3 * len(long_sentences)
    
    return max(0, score), issues


# ─── Check: Tono de Voz ──────────────────────────────────────────────────
def check_tono_voz(text: str, client_name: str = "") -> Tuple[float, List[str]]:
    """Verifica consistencia de tono y voz de marca."""
    issues = []
    score = 85  # Parte de un puntaje base, se descuenta
    
    # Señales de tono inconsistente
    informal_exclamations = re.findall(r'¡[^!]+!', text)
    if len(informal_exclamations) > 3:
        issues.append(f"⚠️ Demasiadas exclamaciones ({len(informal_exclamations)}). Riesgo de tono demasiado informal.")
        score -= 10
    
    # Uso de jerga técnica excesiva
    jerga = re.findall(r'\b(sinergia|disruptivo|paradigma|empoderar|optimizar|escalar|holístico)\b', text, re.IGNORECASE)
    if len(jerga) > 2:
        issues.append(f"🔧 {len(jerga)} términos de jerga técnica. Considera lenguaje más directo.")
        score -= 5 * len(jerga)
    
    # Beneficio vs Característica
    benefit_phrases = re.findall(r'\b(te (ayuda|permite|ahorra)|puedes| lograrás|obtendrás|descubre cómo)\b', text, re.IGNORECASE)
    feature_phrases = re.findall(r'\b(tiene|incluye|cuenta con|dispone de|ofrece)\b', text, re.IGNORECASE)
    
    if len(feature_phrases) > len(benefit_phrases) * 1.5 and len(feature_phrases) > 3:
        issues.append("🎯 Más características que beneficios. Recuerda: 'vende la transformación, no el producto'.")
        score -= 15
    
    # Tono pasivo excesivo
    passive = re.findall(r'\b(se (puede|debe|recomienda|sugiere|considera)|es (posible|recomendable|importante))\b', text, re.IGNORECASE)
    if len(passive) > 3:
        issues.append(f"🎭 {len(passive)} construcciones en voz pasiva. Usa voz activa para más impacto.")
        score -= 5
    
    return max(0, score), issues


# ─── Check: Claims y Datos ────────────────────────────────────────────────
def check_claims(text: str) -> Tuple[float, List[str]]:
    """Verifica que las afirmaciones tengan respaldo."""
    issues = []
    score = 100
    
    # Claims sin respaldo
    for pattern in CLAIMS_SIN_RESPALDO:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            issues.append(f"🚩 Claim sin respaldo: '{m.strip()}' — Agrega fuente o dato que lo respalde.")
            score -= 15
    
    # Promesas exageradas
    for pattern in PROMESAS_EXAGERADAS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            issues.append(f"🔥 Promesa exagerada: '{m.strip()}' — Puede generar desconfianza.")
            score -= 20
    
    # Números sin contexto
    numbers = re.findall(r'\b(\d+[%x])\b', text)
    for num in numbers:
        # Verificar que el número tenga contexto (comparación, período, fuente)
        surrounding = get_surrounding_text(text, num, 50)
        if not surrounding:
            issues.append(f"📊 Número '{num}' sin contexto claro. ¿Comparado con qué? ¿En qué período?")
            score -= 5
    
    return max(0, score), issues


def get_surrounding_text(text: str, target: str, window: int = 50) -> str:
    """Obtiene texto alrededor de un target para dar contexto."""
    idx = text.find(target)
    if idx == -1:
        return ""
    start = max(0, idx - window)
    end = min(len(text), idx + len(target) + window)
    return text[start:end]


# ─── Check: Estructura y Formato ──────────────────────────────────────────
def check_estructura(text: str) -> Tuple[float, List[str]]:
    """Verifica que el contenido sea escaneable y bien estructurado."""
    issues = []
    score = 100
    
    lines = text.split('\n')
    words = text.split()
    word_count = len(words)
    
    # Heading hierarchy (H1, H2, H3)
    h1_count = len(re.findall(r'^#\s', text, re.MULTILINE))
    h2_count = len(re.findall(r'^##\s', text, re.MULTILINE))
    h3_count = len(re.findall(r'^###\s', text, re.MULTILINE))
    total_headings = h1_count + h2_count + h3_count
    
    if word_count > 300 and total_headings == 0:
        issues.append("📑 Contenido extenso (>300 palabras) sin headings. Agrega H2/H3 para escaneabilidad.")
        score -= 20
    elif word_count > 150 and h2_count == 0:
        issues.append("📑 Sin subtítulos (H2). Divide en secciones con headings descriptivos.")
        score -= 15
    
    # Párrafos muy largos
    paragraphs = [l for l in text.split('\n\n') if len(l.strip()) > 0]
    long_pars = [p for p in paragraphs if len(p.split()) > 100]
    if long_pars:
        issues.append(f"📄 {len(long_pars)} párrafo(s) muy largo(s) (>100 palabras). Divide en párrafos más cortos.")
        score -= 5 * len(long_pars)
    
    # Listas (bullet points)
    has_lists = bool(re.search(r'^\s*[-*+]\s', text, re.MULTILINE))
    if word_count > 400 and not has_lists:
        issues.append("📋 Contenido largo sin listas con viñetas. Las listas mejoran la legibilidad.")
        score -= 5
    
    return max(0, score), issues


# ─── Check: SEO ───────────────────────────────────────────────────────────
def check_seo(text: str, keyword: str = "") -> Tuple[float, List[str]]:
    """Verifica aspectos básicos de SEO."""
    issues = []
    score = 80  # Base más baja porque esto es análisis superficial
    
    if not keyword:
        return score, ["ℹ️ Sin keyword especificada. Saltando review SEO."]
    
    words = text.lower()
    keyword_lower = keyword.lower()
    
    # Keyword en título (primera línea)
    first_line = text.split('\n')[0] if text.split('\n') else ""
    if keyword_lower not in first_line.lower():
        issues.append(f"🔑 Keyword '{keyword}' no está en el título. Agrega la palabra clave principal al inicio.")
        score -= 20
    
    # Keyword density
    kw_count = words.count(keyword_lower)
    word_count = len(words.split())
    if word_count > 0:
        density = (kw_count / word_count) * 100
        if density > 3:
            issues.append(f"📊 Keyword stuffing: '{keyword}' aparece {kw_count} veces ({density:.1f}% del texto). Reduce a <3%.")
            score -= 15
        elif density < 0.5 and word_count > 200:
            issues.append(f"📊 Baja densidad de keyword '{keyword}': {kw_count} apariciones ({density:.1f}%). Considera aumentar ligeramente.")
            score -= 5
    
    return max(0, score), issues


# ─── Check: Calidad General ──────────────────────────────────────────────
def check_calidad_general(text: str, content_type: str = "blog") -> Tuple[float, List[str]]:
    """Evalúa la calidad general y valor para el lector."""
    issues = []
    score = 85  # Base
    
    words = text.split()
    word_count = len(words)
    
    # Longitud adecuada según tipo
    length_ranges = {
        "blog": (500, 2000),
        "email": (100, 500),
        "ad": (30, 150),
        "landing": (200, 800),
        "social": (50, 300),
    }
    
    min_words, max_words = length_ranges.get(content_type, (100, 1000))
    if word_count < min_words:
        issues.append(f"📝 Contenido muy corto para {content_type}: {word_count} palabras (mínimo sugerido: {min_words}).")
        score -= 10
    elif word_count > max_words:
        issues.append(f"📝 Contenido muy largo para {content_type}: {word_count} palabras (máximo sugerido: {max_words}).")
        score -= 5
    
    # Hook / Introducción (primeras 50 palabras)
    intro = " ".join(words[:50])
    hook_indicators = re.findall(r'\b(¿sabías|imagina|descubre|cómo|por qué|el secreto|la verdad)\b', intro, re.IGNORECASE)
    if not hook_indicators and content_type in ("blog", "ad", "email"):
        issues.append("🎣 Sin hook fuerte en la introducción. Las primeras palabras deben enganchar al lector.")
        score -= 10
    
    # Llamada a la acción (CTA)
    cta_indicators = re.findall(r'\b(regístrate|descarga|agenda|reserva|compra|suscríbete|llama|escríbenos|solicita)\b', text, re.IGNORECASE)
    if not cta_indicators and content_type in ("email", "ad", "landing"):
        issues.append("📞 Sin CTA (llamada a la acción). ¿Qué quieres que haga el lector después de leer?")
        score -= 15
    
    # Párrafo inicial demasiado largo (en blogs)
    if content_type == "blog":
        first_para = text.split('\n\n')[0] if '\n\n' in text else text
        if len(first_para.split()) > 80:
            issues.append(f"📄 Primer párrafo muy largo ({len(first_para.split())} palabras). Acorta la introducción.")
            score -= 5
    
    return max(0, score), issues


# ─── Reporte de Calidad ──────────────────────────────────────────────────
def check_promises_fulfilled(text: str) -> List[str]:
    """Verifica que el contenido cumpla lo que promete en el título/intro."""
    issues = []
    
    first_150 = text[:150].lower()
    
    # Si el título promete "X pasos" o "X formas", verificar que existan
    steps_promised = re.findall(r'(\d+)\s*(pasos|formas|maneras|claves|secretos|razones|tips|consejos)', first_150)
    for num, noun in steps_promised:
        count = int(num)
        # Buscar si hay exactamente ese número de items numerados
        numbered = len(re.findall(r'^\d+\.\s', text, re.MULTILINE))
        items = len(re.findall(r'^\s*[-*+]\s', text, re.MULTILINE))
        if numbered < count and items < count:
            issues.append(f"🎯 El título promete '{count} {noun}' pero solo encontramos {max(numbered, items)} elementos.")
    
    return issues


def generate_report(text: str, client_name: str = "", keyword: str = "", content_type: str = "blog") -> dict:
    """Genera el reporte completo de calidad."""
    
    checks = {
        "ortografia": check_ortografia(text),
        "tono_voz": check_tono_voz(text, client_name),
        "claims": check_claims(text),
        "estructura": check_estructura(text),
        "seo": check_seo(text, keyword),
        "calidad_general": check_calidad_general(text, content_type),
    }
    
    # Calcular score ponderado
    weighted_score = 0
    all_issues = []
    details = {}
    
    for check_name, (score, issues) in checks.items():
        weight = SCORE_WEIGHTS.get(check_name, 0.1)
        weighted_score += score * weight
        all_issues.extend(issues)
        details[check_name] = {
            "score": score,
            "weight": weight,
            "weighted_contribution": round(score * weight, 1),
            "issues": issues
        }
    
    # Promesas
    promise_issues = check_promises_fulfilled(text)
    all_issues.extend(promise_issues)
    
    final_score = round(weighted_score, 1)
    
    return {
        "score": final_score,
        "veredicto": "✅ APROBADO" if final_score >= UMBRAL_APROBACION else (
            "🔄 NECESITA MEJORAS" if final_score >= UMBRAL_CRITICO else "❌ DEVUELTO A PIPELINE"
        ),
        "detalles": details,
        "issues": all_issues,
        "promesas_incumplidas": promise_issues,
        "resumen_ejecutivo": generate_summary(final_score, all_issues, content_type),
        "estadisticas": {
            "palabras": len(text.split()),
            "oraciones": len(re.split(r'[.!?]+', text)) - 1,
            "parrafos": len([p for p in text.split('\n\n') if p.strip()]),
            "headings": len(re.findall(r'^#{1,3}\s', text, re.MULTILINE)),
        }
    }


def generate_summary(score: float, issues: List[str], content_type: str) -> str:
    """Genera un resumen ejecutivo del reporte."""
    if score >= UMBRAL_APROBACION:
        if not issues:
            return "✅ Contenido listo para revisión humana. Sin issues detectados."
        return f"✅ Score: {score}/100. {len(issues)} issues menores. Listo para revisión humana."
    elif score >= UMBRAL_CRITICO:
        return f"🔄 Score: {score}/100. {len(issues)} issues. Requiere mejoras antes de enviar a revisión."
    else:
        return f"❌ Score: {score}/100. {len(issues)} issues críticos. Devolver al pipeline de generación."


# ─── Integración con Pulsar ──────────────────────────────────────────────
def send_to_pulsar(report: dict, content_body: str, platform: str = "blog", title: str = "") -> bool:
    """
    Si el score supera el umbral, envía el contenido a Pulsar como pending_review.
    """
    if report["score"] < UMBRAL_APROBACION:
        print(f"      ⏭️  Score {report['score']} < umbral {UMBRAL_APROBACION}. No enviado a Pulsar.")
        return False
    
    if not os.path.exists(PULSAR_DB):
        print(f"      ⚠️  Base de datos Pulsar no encontrada en {PULSAR_DB}")
        return False
    
    try:
        conn = sqlite3.connect(str(PULSAR_DB))
        cursor = conn.cursor()
        
        # Verificar que existe la tabla content_items
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='content_items'")
        if not cursor.fetchone():
            conn.close()
            print(f"      ⚠️  Tabla content_items no existe en Pulsar DB")
            return False
        
        from datetime import timezone
        now = datetime.now(timezone.utc).isoformat()
        
        # Buscar un workspace activo
        cursor.execute("SELECT id, name FROM workspaces WHERE active = 1 LIMIT 1")
        workspace = cursor.fetchone()
        if not workspace:
            print(f"      ⚠️  No hay workspaces activos en Pulsar")
            conn.close()
            return False
        
        workspace_id, workspace_name = workspace
        
        # Crear ContentItem
        import uuid
        content_id = uuid.uuid4().hex[:12]
        
        cursor.execute(
            """INSERT INTO content_items (id, workspace_id, platform, title, body, status, current_version, created_by)
               VALUES (?, ?, ?, ?, ?, 'in_review', 1, 'quality-engine')""",
            (content_id, workspace_id, platform, title[:255], content_body)
        )
        
        # Crear primera versión
        version_id = uuid.uuid4().hex[:12]
        cursor.execute(
            """INSERT INTO content_versions (id, content_id, version, body, status, change_summary, created_by)
               VALUES (?, ?, 1, ?, 'pending_review', ?, 'quality-engine')""",
            (
                version_id, content_id, content_body,
                f"Quality Engine v1 | Score: {report['score']}/100 | Issues: {len(report['issues'])}"
            )
        )
        
        conn.commit()
        conn.close()
        
        print(f"      ✅ Enviado a Pulsar: content_id={content_id} | workspace={workspace_name}")
        print(f"      📋 Status: in_review | Version status: pending_review")
        print(f"      🔗 Pulsar URL: http://pulsar.polaris.pw:8081/content/{content_id}")
        return True
        
    except Exception as e:
        print(f"      ❌ Error enviando a Pulsar: {e}")
        return False


# ─── Main ─────────────────────────────────────────────────────────────────
def run_quality_check(content: str, client_name: str = "", keyword: str = "",
                      content_type: str = "blog", title: str = "",
                      send_to_pulsar_flag: bool = False, platform: str = "blog"):
    
    print(f"\n{'='*60}")
    print(f"  🎯 QUALITY ENGINE — Revisión de Contenido")
    print(f"  Tipo: {content_type.upper()} | Keywords: {keyword or 'ninguna'}")
    print(f"{'='*60}\n")
    
    report = generate_report(content, client_name, keyword, content_type)
    
    # Score y veredicto
    score_color = "🟢" if report["score"] >= UMBRAL_APROBACION else ("🟡" if report["score"] >= UMBRAL_CRITICO else "🔴")
    print(f"  {score_color} SCORE GLOBAL: {report['score']}/100")
    print(f"  📋 VEREDICTO: {report['veredicto']}")
    print(f"  📊 Estadísticas: {report['estadisticas']['palabras']} palabras, "
          f"{report['estadisticas']['oraciones']} oraciones, "
          f"{report['estadisticas']['headings']} headings\n")
    
    # Detalles por check
    print(f"  {'─'*56}")
    print(f"  {'Check':<25} {'Score':>8} {'Peso':>6} {'Contrib.':>10}")
    print(f"  {'─'*56}")
    for check_name, detail in report["detalles"].items():
        name = check_name.replace("_", " ").title()
        bar = "█" * max(1, int(detail["score"] / 10))
        print(f"  {name:<25} {detail['score']:>4}/100 {detail['weight']:>4.0%} {detail['weighted_contribution']:>8.1f}  {bar}")
    print(f"  {'─'*56}\n")
    
    # Issues encontrados
    if report["issues"]:
        print(f"  ⚠️  Issues encontrados ({len(report['issues'])}):")
        for i, issue in enumerate(report["issues"], 1):
            print(f"    {i:2d}. {issue}")
    else:
        print(f"  ✅ Ningún issue detectado. Contenido limpio.")
    
    print()
    
    # Enviar a Pulsar si aplica
    if send_to_pulsar_flag:
        print(f"  📤 Enviando a Pulsar...")
        sent = send_to_pulsar(report, content, platform, title)
        if not sent:
            print(f"  💾 Guardando reporte localmente...")
    
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Quality Engine — Revisión de Contenido")
    parser.add_argument("--content", help="Texto del contenido a revisar")
    parser.add_argument("--file", help="Archivo con el contenido a revisar")
    parser.add_argument("--client-name", default="")
    parser.add_argument("--keyword", default="", help="Palabra clave principal para SEO")
    parser.add_argument("--type", default="blog", choices=["blog", "email", "ad", "landing", "social"],
                        help="Tipo de contenido")
    parser.add_argument("--title", default="", help="Título del contenido")
    parser.add_argument("--send-to-pulsar", action="store_true", help="Enviar a Pulsar si pasa QA")
    parser.add_argument("--platform", default="blog", help="Plataforma para Pulsar")
    
    args = parser.parse_args()
    
    # Leer contenido
    if args.content:
        content = args.content
    elif args.file:
        with open(args.file) as f:
            content = f.read()
    else:
        # Leer desde stdin
        content = sys.stdin.read()
    
    if not content.strip():
        print("❌ No se proporcionó contenido. Usa --content, --file, o pipea texto a stdin.")
        sys.exit(1)
    
    run_quality_check(content, args.client_name, args.keyword, args.type,
                      args.title, args.send_to_pulsar, args.platform)