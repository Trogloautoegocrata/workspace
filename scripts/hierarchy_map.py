#!/usr/bin/env python3
"""
hierarchy_map.py — SISTEMA MANUAL + AUTOMÁTICO para asignar h1-h6 a texto plano.

Concepto:
- MAPEO MANUAL de secciones lógicas por artículo (un JSON config por post)
- DETECCIÓN AUTOMÁTICA de marcadores débiles como h4-h6
- Aplicación robusta con jerarquía válida (no saltar niveles)

Uso:
    python3 hierarchy_map.py <input.html> <output.html> --map=path/to/map.json
    python3 hierarchy_map.py <input.html> <output.html> --auto  # solo automático

Formato del map.json:
{
  "h2": ["Rangos de Precio por Tipo de Web", "Plantilla vs Diseño", ...],
  "h3": ["Tipos", "Básica", "Corporativa", "E-commerce", ...],
  "h4_starts_with": ["Por qué", "Cómo", "Ejemplo:", "Caso:"],
  "h5_starts_with": ["Nota:", "Tip:", "Importante:", "Aclaración:"],
  "h6_starts_with": ["Fuente:", "Anexo:", "Disclaimer:"]
}
"""
import re
import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Set


def is_likely_heading_text(text: str, max_length: int = 100) -> bool:
    """Heurística: ¿este párrafo es probablemente un heading?"""
    text = text.strip()
    if not text or len(text) > max_length:
        return False
    if text.endswith(('.', '?', '!')) and len(text) > 60:
        return False
    words = text.split()
    if len(words) > 12:
        return False
    if text.lower() in {'y', 'o', 'de', 'la', 'el', 'los', 'las', 'a', 'en', 'por', 'para', 'con', 'sin'}:
        return False
    return True


def find_article_body(html: str) -> Optional[Tuple[int, int, str, str]]:
    """Encuentra el inicio/fin del body del artículo."""
    # 1. <div class="post-content">
    m = re.search(
        r'(<div class="post-content"[^>]*>)(.*?)(</div>\s*</article>|</div>\s*<nav|</div>\s*<div class="author-bio"|</div>\s*<div class="related-posts")',
        html, re.DOTALL
    )
    if m:
        return (m.start(2), m.end(2), m.group(1), m.group(3))
    # 2. <article>
    m = re.search(r'(<article[^>]*>)(.*?)(</article>)', html, re.DOTALL)
    if m:
        return (m.start(2), m.end(2), m.group(1), m.group(3))
    return None


def find_paragraphs(body: str) -> List[Dict]:
    """Tokeniza el body en párrafos y headings."""
    elements = []
    pattern = re.compile(
        r'<(p|h[1-6])([^>]*)>(.*?)</\1>|<(img|hr|ul|ol|table|figure|blockquote)([^>]*)>',
        re.DOTALL | re.IGNORECASE
    )
    for m in pattern.finditer(body):
        if m.group(1):
            tag = m.group(1).lower()
            attrs = m.group(2)
            content = m.group(3)
            elements.append({
                'type': tag,
                'attrs': attrs,
                'content': content,
                'clean_text': re.sub(r'<[^>]+>', '', content).strip(),
                'start': m.start(),
                'end': m.end(),
            })
        else:
            elements.append({
                'type': m.group(4).lower(),
                'attrs': m.group(5),
                'content': '',
                'clean_text': '',
                'start': m.start(),
                'end': m.end(),
            })
    return elements


def apply_manual_map(elements: List[Dict], map_config: Dict) -> List[Dict]:
    """Aplica el mapa manual de headings."""
    import unicodedata
    h2_set = set()
    for h in map_config.get('h2', []):
        # Normalizar: lowercase, strip, reemplazar NBSP y guiones invisibles
        norm = h.lower().strip()
        norm = norm.replace('\xa0', ' ').replace('\u200b', '').replace('\u200d', '')
        h2_set.add(norm)
    h2_pattern_starts = map_config.get('h2_pattern_starts', [])
    h3_set = set()
    for h in map_config.get('h3', []):
        norm = h.lower().strip().replace('\xa0', ' ').replace('\u200b', '').replace('\u200d', '')
        h3_set.add(norm)
    h4_starts = map_config.get('h4_starts_with', [])
    h5_starts = map_config.get('h5_starts_with', [])
    h6_starts = map_config.get('h6_starts_with', [])

    last_h = 0
    skip_next = False  # Si el párrafo actual es "Capítulo N", el siguiente es h2
    for el in elements:
        if el['type'] != 'p':
            continue
        if not el['clean_text']:
            continue
        text = el['clean_text']
        # Normalizar el texto del párrafo
        text_norm = text.replace('\xa0', ' ').replace('\u200b', '').replace('\u200d', '')
        text_lower = text_norm.lower().strip()

        # Si el párrafo anterior fue "Capítulo N", este es h2
        if skip_next and is_likely_heading_text(text_norm, max_length=120):
            slug = re.sub(r'[^a-z0-9]+', '-', text_norm.lower()).strip('-')[:50]
            el['new_tag'] = 'h2'
            el['new_id'] = slug
            el['new_level'] = 2
            last_h = 2
            skip_next = False
            continue
        skip_next = False

        # Skip si el párrafo es muy largo
        if not is_likely_heading_text(text_norm):
            continue

        # Detectar "Capítulo N" → siguiente párrafo será h2
        if any(text_norm.startswith(p) for p in h2_pattern_starts) and len(text_norm) < 20:
            skip_next = True
            continue

        assigned = None

        # H2 exacto
        if text_lower in h2_set or any(text_lower.startswith(h) for h in h2_set):
            assigned = 2
        # H3 exacto
        elif text_lower in h3_set or any(text_lower.startswith(h) for h in h3_set):
            assigned = 3
        # H4 starts_with
        elif any(text_norm.startswith(p) for p in h4_starts):
            assigned = 4
        # H5 starts_with
        elif any(text_norm.startswith(p) for p in h5_starts):
            assigned = 5
        # H6 starts_with
        elif any(text_norm.startswith(p) for p in h6_starts):
            assigned = 6

        if assigned:
            # Validar jerarquía
            if last_h == 0:
                assigned = min(assigned, 2)
            elif assigned > last_h + 1:
                assigned = last_h + 1
            slug = re.sub(r'[^a-z0-9]+', '-', text_norm.lower()).strip('-')[:50]
            el['new_tag'] = f'h{assigned}'
            el['new_id'] = slug
            el['new_level'] = assigned
            last_h = assigned
    return elements


def apply_auto_only(elements: List[Dict]) -> List[Dict]:
    """Aplica detección automática pura (sin mapa manual)."""
    last_h = 0
    for el in elements:
        if el['type'] != 'p':
            continue
        if not el['clean_text']:
            continue
        text = el['clean_text']
        if not is_likely_heading_text(text):
            continue

        # Patrones automáticos
        assigned = None
        # H2: "Capítulo N", "Sección N", "Conclusión", "Introducción", "Resumen", "1. Title", "FAQ"
        if re.match(r'^(Introducción|Conclusión|Resumen|Recomendaciones|FAQ|Preguntas Frecuentes)$', text, re.IGNORECASE):
            assigned = 2
        elif re.match(r'^(?:[Cc]apítulo|[Ss]ección|[Pp]arte)\s+[IVX0-9]+', text):
            assigned = 2
        elif re.match(r'^\d+\.\s+[A-ZÁÉÍÓÚÑ].{5,80}$', text):
            assigned = 2
        elif re.match(r'^(Glosario|Herramientas|Recursos|Tendencias|Panorama|Comparativa|Análisis|Framework|Guía|Metodología|Proceso|Cómo|Cuándo|Dónde|Por qué|Qué es)', text, re.IGNORECASE):
            assigned = 2
        # H3
        elif re.match(r'^(Tipos?|Categorías?|Ejemplos?|Ventajas?|Desventajas?|Beneficios?|Riesgos?|Causas?|Síntomas?|Casos? de [a-z]+)$', text, re.IGNORECASE):
            assigned = 3
        elif re.match(r'^[🔢💡⚠️📊✅❌⭐]\s*[A-ZÁÉÍÓÚÑ].{3,60}$', text):
            assigned = 3
        # H4
        elif re.match(r'^(?:[a-z]\)|[-•])\s+[A-Z].{5,80}$', text):
            assigned = 4
        # H5
        elif re.match(r'^(Nota|Tip|Aclaración|Importante|Ojo):', text, re.IGNORECASE):
            assigned = 5
        # H6
        elif re.match(r'^(Fuente|Fuentes?|Bibliografía|Referencias|Disclaimer|Anexo):', text, re.IGNORECASE):
            assigned = 6

        if assigned:
            if last_h == 0:
                assigned = min(assigned, 2)
            elif assigned > last_h + 1:
                assigned = last_h + 1
            slug = re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')[:50]
            el['new_tag'] = f'h{assigned}'
            el['new_id'] = slug
            el['new_level'] = assigned
            last_h = assigned
    return elements


def render_html(elements: List[Dict], original_body: str) -> str:
    """Re-renderiza el body con los nuevos headings."""
    parts = []
    pos = 0
    for el in elements:
        if el['start'] > pos:
            parts.append(original_body[pos:el['start']])
        if 'new_tag' in el:
            content = el['content']
            new_tag = el['new_tag']
            new_id = el['new_id']
            replacement = f'<{new_tag} id="{new_id}">{content}</{new_tag}>'
            parts.append(replacement)
        else:
            # Mantener el elemento original
            if el['type'] == 'p':
                parts.append(f'<p{el["attrs"]}>{el["content"]}</p>')
            else:
                parts.append(f'<{el["type"]}{el["attrs"]}>')
        pos = el['end']
    if pos < len(original_body):
        parts.append(original_body[pos:])
    return ''.join(parts)


def generate_toc(elements: List[Dict]) -> str:
    """Genera un TOC automático desde los headings."""
    toc_items = [el for el in elements if 'new_tag' in el]
    if not toc_items:
        return ''

    toc_html = ['<nav class="toc" aria-label="Tabla de contenidos">']
    toc_html.append('<details open>')
    toc_html.append('<summary>📑 Tabla de contenidos</summary>')
    toc_html.append('<ol>')

    for el in toc_items:
        level = el.get('new_level', 2)
        indent = '  ' * (level - 2)
        toc_html.append(f'{indent}<li><a href="#{el["new_id"]}">{el["clean_text"][:60]}</a></li>')

    toc_html.append('</ol>')
    toc_html.append('</details>')
    toc_html.append('</nav>')
    return '\n'.join(toc_html)


def add_hierarchy_css(html: str) -> str:
    """Inyecta CSS para h1-h6 si no existe."""
    css_block = """
<style>
.post-content h1, .article-content h1, .post-body h1 {
    font-family: 'DM Sans', sans-serif;
    font-weight: 800;
    font-size: clamp(2rem, 4vw, 2.75rem);
    line-height: 1.1;
    letter-spacing: -0.03em;
    margin: 3.5rem 0 1.5rem;
    color: #e5e5e9;
}
.post-content h2, .article-content h2, .post-body h2 {
    font-family: 'DM Sans', sans-serif;
    font-weight: 700;
    font-size: clamp(1.6rem, 3.5vw, 2.1rem);
    line-height: 1.15;
    letter-spacing: -0.025em;
    margin: 3rem 0 1.25rem;
    color: #e5e5e9;
    border-left: 3px solid #1edb7f;
    padding-left: 1rem;
}
.post-content h3, .article-content h3, .post-body h3 {
    font-family: 'Inter', sans-serif;
    font-weight: 700;
    font-size: clamp(1.2rem, 2.5vw, 1.5rem);
    line-height: 1.25;
    letter-spacing: -0.015em;
    margin: 2.25rem 0 1rem;
    color: #e5e5e9;
}
.post-content h4, .article-content h4, .post-body h4 {
    font-family: 'Inter', sans-serif;
    font-weight: 600;
    font-size: clamp(1.05rem, 2vw, 1.2rem);
    line-height: 1.3;
    margin: 1.75rem 0 0.75rem;
    color: #1edb7f;
}
.post-content h5, .article-content h5, .post-body h5 {
    font-family: 'Inter', sans-serif;
    font-weight: 600;
    font-size: clamp(0.95rem, 1.5vw, 1.05rem);
    line-height: 1.4;
    margin: 1.25rem 0 0.5rem;
    color: #e5e5e9;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.post-content h6, .article-content h6, .post-body h6 {
    font-family: 'Inter', sans-serif;
    font-weight: 500;
    font-size: 0.875rem;
    line-height: 1.5;
    margin: 1rem 0 0.5rem;
    color: #8b8b95;
    font-style: italic;
}
.toc {
    background: rgba(30, 30, 46, 0.5);
    border: 1px solid #1e1e2e;
    border-radius: 12px;
    padding: 1.5rem;
    margin: 2rem 0 3rem;
    font-size: 0.9rem;
}
.toc summary {
    cursor: pointer;
    font-weight: 600;
    color: #1edb7f;
    margin-bottom: 1rem;
    user-select: none;
}
.toc ol {
    list-style: none;
    padding-left: 0;
    margin: 0;
}
.toc li {
    margin: 0.4rem 0;
    line-height: 1.4;
}
.toc li a {
    color: #8b8b95;
    text-decoration: none;
    transition: color 0.2s;
}
.toc li a:hover { color: #1edb7f; }
.toc li li { padding-left: 1.5rem; font-size: 0.85rem; }
</style>
"""
    if 'post-content h2 {' in html or '.post-content h2 {' in html:
        return html
    # Insertar antes de </head>
    return html.replace('</head>', css_block + '\n</head>', 1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('input')
    parser.add_argument('output')
    parser.add_argument('--map', help='JSON con mapa manual de headings')
    parser.add_argument('--auto', action='store_true', help='Solo auto-detección')
    args = parser.parse_args()

    html = Path(args.input).read_text(encoding='utf-8')
    print(f'Leyendo {args.input} ({len(html)} bytes)')

    article = find_article_body(html)
    if not article:
        print('ERROR: no se encontró el body del artículo')
        sys.exit(1)

    body_start, body_end, head_marker, tail_marker = article
    body = html[body_start:body_end]

    elements = find_paragraphs(body)
    print(f'Encontrados {len(elements)} elementos')

    if args.map:
        map_config = json.loads(Path(args.map).read_text(encoding='utf-8'))
        elements = apply_manual_map(elements, map_config)
        print(f'Aplicado mapa manual')
    else:
        elements = apply_auto_only(elements)
        print(f'Aplicada auto-detección')

    new_body = render_html(elements, body)
    toc = generate_toc(elements)

    # Insertar TOC después del primer párrafo
    if toc:
        # Buscar el primer <p> o <h*> del body
        first_p = re.search(r'(<p[^>]*>.*?</p>|<h[1-6][^>]*>.*?</h[1-6]>)', new_body, re.DOTALL)
        if first_p:
            new_body = new_body[:first_p.end()] + '\n' + toc + '\n' + new_body[first_p.end():]
        else:
            new_body = toc + '\n' + new_body

    new_html = html[:body_start] + new_body + html[body_end:]

    # Añadir CSS si no existe
    new_html = add_hierarchy_css(new_html)

    Path(args.output).write_text(new_html, encoding='utf-8')
    print(f'\nGenerado {args.output} ({len(new_html)} bytes)')

    # Log
    headings = [el for el in elements if 'new_tag' in el]
    print(f'\nHeadings aplicados: {len(headings)}')
    by_level = {}
    for el in headings:
        by_level.setdefault(el['new_level'], 0)
        by_level[el['new_level']] += 1
    for level, count in sorted(by_level.items()):
        print(f'  h{level}: {count}')


if __name__ == '__main__':
    main()
