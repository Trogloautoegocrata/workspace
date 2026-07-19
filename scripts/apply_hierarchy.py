#!/usr/bin/env python3
"""
apply_hierarchy.py — SISTEMA para asignar h1-h6 a texto plano en artículos de blog.

Uso:
    python3 apply_hierarchy.py <input.html> <output.html> [--config=config.json]

El sistema:
1. Lee el HTML y extrae solo el contenido del artículo (<article>, .post-content, .post-body)
2. Detecta "marcadores de jerarquía" usando reglas configurables:
   - Líneas con patrón "##", "###" markdown
   - Texto corto solo en su línea que coincide con keywords (Conclusión, Capítulo, etc.)
   - Numeración (1., 2., 3.) en línea sola
3. Aplica heurísticas de nivel:
   - Patrones "Capítulo N" → h2
   - "Sección N" → h2
   - Keywords como "Conclusión", "Introducción" → h2
   - Numeración simple "1. ", "2. " → h3
   - Preguntas en su línea → h3 o h4
4. Inyecta los headings al HTML
5. Genera un TOC automático
6. Reporta log de cambios
"""
import re
import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict, Tuple, Optional


# ─── Reglas de detección ──────────────────────────────────────────────────────
H2_PATTERNS = [
    r'^(Introducción|Conclusión|Resumen|Resumen Final|Recomendaciones|Casos de (?:éxito|estudio)|FAQ|Preguntas Frecuentes)$',
    r'^(?:[Cc]apítulo|[Ss]ección|[Pp]arte)\s+[IVX0-9]+',
    r'^\d+\.\s+[A-ZÁÉÍÓÚÑ].{5,80}$',  # "1. Hechos rápidos..."
    r'^(Glosario|Herramientas|Recursos|Tendencias|Panorama|Comparativa|Análisis|Framework|Guía|Metodología|Proceso|Cómo|Cuándo|Dónde|Por qué|Qué es)',
]
H3_PATTERNS = [
    r'^(Tipos?|Categorías?|Ejemplos?|Ventajas?|Desventajas?|Beneficios?|Riesgos?|Causas?|Síntomas?|Mitos? y Realidades?)$',
    r'^[🔢💡⚠️📊✅❌⭐]\s*[A-ZÁÉÍÓÚÑ].{3,60}$',
]
H4_PATTERNS = [
    r'^(?:[a-z]\)|[-•])\s+[A-Z].{5,80}$',
]
H5_PATTERNS = [
    r'^(Nota|Tip|Aclaración|Importante|Ojo):',
]
H6_PATTERNS = [
    r'^(Fuente|Fuentes?|Bibliografía|Referencias|Disclaimer|Anexo):',
]

# Keywords que indican fin de bloque (no es heading)
STOPWORDS = {'y', 'o', 'de', 'la', 'el', 'los', 'las', 'a', 'en', 'por', 'para', 'con', 'sin'}


def is_likely_heading(text: str, max_length: int = 100) -> bool:
    """Heurística: ¿este párrafo es probablemente un heading?"""
    text = text.strip()
    if not text:
        return False
    if len(text) > max_length:
        return False
    if text.endswith(('.', '?', '!')) and len(text) > 60:
        return False  # Oraciones largas rara vez son headings
    if text.lower() in STOPWORDS:
        return False
    # Si tiene más de 5 palabras Y no termina en signo de puntuación, probablemente es texto
    words = text.split()
    if len(words) > 12:
        return False
    return True


def classify_heading(text: str) -> Optional[int]:
    """Devuelve el nivel de heading (1-6) o None si no es heading."""
    text = text.strip()
    if not is_likely_heading(text):
        return None

    for pattern in H2_PATTERNS:
        if re.match(pattern, text):
            return 2
    for pattern in H3_PATTERNS:
        if re.match(pattern, text):
            return 3
    for pattern in H4_PATTERNS:
        if re.match(pattern, text):
            return 4
    for pattern in H5_PATTERNS:
        if re.match(pattern, text):
            return 5
    for pattern in H6_PATTERNS:
        if re.match(pattern, text):
            return 6
    return None


def extract_paragraphs(html: str) -> List[Tuple[str, str]]:
    """
    Extrae párrafos del HTML. Devuelve lista de (tipo, contenido) donde tipo es:
    'p' = <p> tag
    'tag' = otros tags
    'text' = texto suelto
    """
    result = []
    # Encontrar el body del artículo
    article_match = re.search(
        r'(<div class="post-content"[^>]*>)(.*?)(</div>\s*</article>|</div>\s*<div class="author-bio)',
        html, re.DOTALL
    )
    if not article_match:
        # Fallback: buscar el primer <article>
        article_match = re.search(
            r'(<article[^>]*>)(.*?)(</article>)', html, re.DOTALL
        )
    if not article_match:
        return []

    body = article_match.group(2)
    # Tokenizar por tags <p> y <h*>
    pattern = re.compile(r'<(p|h[1-6])([^>]*)>(.*?)</\1>|<(img|hr|ul|ol|table|figure|blockquote)([^>]*)>', re.DOTALL | re.IGNORECASE)
    for m in pattern.finditer(body):
        if m.group(1):
            tag = m.group(1).lower()
            attrs = m.group(2)
            content = m.group(3).strip()
            result.append((tag, attrs, content))
        elif m.group(4):
            result.append((m.group(4).lower(), m.group(5), ''))
    return result


def apply_hierarchy(html: str, custom_rules: Optional[Dict] = None) -> Tuple[str, List[str]]:
    """
    Aplica jerarquía h1-h6 al HTML. Devuelve (nuevo_html, lista de headings aplicados).
    """
    log = []
    # Encontrar el body del artículo
    article_match = re.search(
        r'(<div class="post-content"[^>]*>)(.*?)(</div>\s*</article>|</div>\s*<nav|</div>\s*<div class="author-bio)',
        html, re.DOTALL
    )
    if not article_match:
        article_match = re.search(
            r'(<article[^>]*>)(.*?)(</article>)', html, re.DOTALL
        )
    if not article_match:
        return html, ['ERROR: no se encontró <article> ni .post-content']

    head = article_match.group(1)
    body = article_match.group(2)
    tail = article_match.group(3)

    # Tokenizar y reemplazar
    new_body_parts = []
    last_h_level = 0
    headings_added = 0

    # Regex para capturar <p ...>contenido</p> o <h*>
    pattern = re.compile(
        r'<(p|h[1-6])([^>]*)>(.*?)</\1>|<(img|hr|ul|ol|table|figure|blockquote)([^>]*)>',
        re.DOTALL | re.IGNORECASE
    )

    pos = 0
    for m in pattern.finditer(body):
        # Añadir lo que hay entre matches
        if m.start() > pos:
            new_body_parts.append(body[pos:m.start()])
        pos = m.end()

        if m.group(1):
            tag = m.group(1).lower()
            attrs = m.group(2)
            content = m.group(3).strip()

            if tag == 'p' and content:
                # Limpiar el contenido de tags internos para análisis
                clean = re.sub(r'<[^>]+>', '', content).strip()
                if clean:
                    level = classify_heading(clean)
                    if level:
                        # Verificar jerarquía válida (no saltar más de 1 nivel)
                        if last_h_level == 0:
                            level = min(level, 2)  # El primero debe ser h2
                        elif level > last_h_level + 1:
                            level = last_h_level + 1  # No saltar niveles
                        slug = re.sub(r'[^a-z0-9]+', '-', clean.lower()).strip('-')[:50]
                        heading = f'<h{level} id="{slug}">{clean}</h{level}>'
                        new_body_parts.append(heading)
                        log.append(f'  h{level}: {clean[:60]}')
                        last_h_level = level
                        headings_added += 1
                        continue
                new_body_parts.append(f'<{tag}{attrs}>{content}</{tag}>')
            else:
                # Ya era un heading, mantener
                new_body_parts.append(f'<{tag}{attrs}>{content}</{tag}>')
                level_num = int(tag[1]) if tag[1:].isdigit() else 0
                if level_num:
                    last_h_level = level_num
        else:
            # Tag self-closing o de bloque
            new_body_parts.append(m.group(0))

    if pos < len(body):
        new_body_parts.append(body[pos:])

    new_body = ''.join(new_body_parts)
    new_html = html[:article_match.start()] + head + new_body + tail + html[article_match.end():]
    log.insert(0, f'Aplicados: {headings_added} headings')
    return new_html, log


def main():
    parser = argparse.ArgumentParser(description='Sistema de jerarquías h1-h6 para artículos de blog')
    parser.add_argument('input', help='HTML de entrada')
    parser.add_argument('output', help='HTML de salida')
    parser.add_argument('--config', help='JSON con reglas personalizadas', default=None)
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    if not input_path.exists():
        print(f'ERROR: no existe {input_path}')
        sys.exit(1)

    html = input_path.read_text(encoding='utf-8')
    print(f'Leyendo {input_path} ({len(html)} bytes)...')

    new_html, log = apply_hierarchy(html)
    output_path.write_text(new_html, encoding='utf-8')
    print(f'\nGenerado {output_path} ({len(new_html)} bytes)')
    print('\nLog de headings:')
    for line in log:
        print(line)


if __name__ == '__main__':
    main()
