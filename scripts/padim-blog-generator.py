#!/usr/bin/env python3
"""
padim-blog-generator.py — Generador de blog estático para PADIM
v1.1.0 - 12 Jul 2026
- Tab system por audiencia (tabs con colores, URL hash, localStorage)
- Fallback: sin JS se ven todas las secciones
"""

import os, re, json, math
from pathlib import Path
from datetime import datetime
from html import escape

# ── CONFIG ──
BASE_DIR = Path("/home/polaris/workspace/public/blog-padim")
POSTS_DIR = BASE_DIR / "posts"
OUTPUT_DIR = BASE_DIR
SITE_NAME = "PADIM Blog"
SITE_URL = "http://blog.enmexico.casa:8081"
SITE_DESC = "Explorando el futuro de los datos inmobiliarios en México"

DESIGN_TOKENS = """
:root {
  --bg-base: #07070d;
  --bg-card: #0d0d18;
  --bg-card-hover: #141425;
  --bg-elevated: #111122;
  --border: #1a1a30;
  --border-hover: #252545;
  --text: #e0e0e8;
  --text-muted: #9090a8;
  --text-subtle: #606078;
  --accent: #6BCFDB;
  --accent-hover: #8adce8;
  --accent-dim: rgba(107,207,219,0.08);
  --green: #5FC577;
  --blue: #5B8DEF;
  --purple: #A96FE6;
  --amber: #E8B339;
  --radius: 0.75rem;
  --radius-sm: 0.375rem;
  --font-sans: 'Inter',-apple-system,BlinkMacSystemFont,sans-serif;
  --font-mono: 'JetBrains Mono','Fira Code',monospace;
  --max-width: 800px;
}
"""

AUDIENCIA_TAGS = {
    "Académico":  {"color": "#A96FE6", "emoji": "🟣", "id": "academico",  "cls": "tab-academico"},
    "Técnico":    {"color": "#5B8DEF", "emoji": "🔵", "id": "tecnico",    "cls": "tab-tecnico"},
    "Profesional":{"color": "#5FC577", "emoji": "🟢", "id": "profesional","cls": "tab-profesional"},
    "General":    {"color": "#9090a8", "emoji": "⚪", "id": "general",    "cls": "tab-general"},
}

# Auditoría: qué secciones pertenecen a qué audiencia
SECTION_MAP = {
    "🟣": "Académico",
    "🔵": "Técnico",
    "🟢": "Profesional",
    "⚪": "General",
}


def parse_frontmatter(text):
    m = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', text, re.DOTALL)
    if not m:
        return {}, text
    fm = {}
    for line in m.group(1).split('\n'):
        line = line.strip()
        if ':' in line:
            key, val = line.split(':', 1)
            key, val = key.strip(), val.strip()
            if val.startswith('[') and val.endswith(']'):
                val = [v.strip().strip('"\'').strip("'") for v in val[1:-1].split(',')]
            elif val.lower() == 'true': val = True
            elif val.lower() == 'false': val = False
            elif val.isdigit(): val = int(val)
            fm[key] = val
    return fm, m.group(2)


def md_to_html(text):
    lines = text.split('\n')
    out = []
    in_code = False
    in_list = False
    in_table = False
    table_buf = []

    i = 0
    while i < len(lines):
        line = lines[i]

        if line.startswith('```'):
            if in_code:
                out.append('</code></pre>')
                in_code = False
            else:
                lang = line[3:].strip()
                out.append(f'<pre><code class="language-{lang}">')
                in_code = True
            i += 1
            continue

        if in_code:
            out.append(escape(line))
            i += 1
            continue

        # Tables
        if line.strip().startswith('|') and (i + 1 < len(lines) and lines[i+1].strip().startswith('|')):
            table_buf = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                table_buf.append(lines[i])
                i += 1
            out.append(parse_table(table_buf))
            continue

        if line.strip() == '':
            if in_list:
                out.append('</ul>' if in_list == 'ul' else '</ol>')
                in_list = False
            out.append('')
            i += 1
            continue

        if line.startswith('### '):
            if in_list: out.append('</ul>' if in_list == 'ul' else '</ol>'); in_list = False
            out.append(f'<h3>{escape(line[4:])}</h3>')
        elif line.startswith('## '):
            if in_list: out.append('</ul>' if in_list == 'ul' else '</ol>'); in_list = False
            out.append(f'<h2>{escape(line[3:])}</h2>')
        elif line.startswith('# '):
            if in_list: out.append('</ul>' if in_list == 'ul' else '</ol>'); in_list = False
            out.append(f'<h1>{escape(line[2:])}</h1>')
        elif line.startswith('- '):
            if not in_list: out.append('<ul>'); in_list = 'ul'
            out.append(f'<li>{md_inline(line[2:])}</li>')
        elif line.startswith('1. '):
            if not in_list: out.append('<ol>'); in_list = 'ol'
            out.append(f'<li>{md_inline(line[3:])}</li>')
        else:
            if in_list: out.append('</ul>' if in_list == 'ul' else '</ol>'); in_list = False
            if line.strip():
                out.append(f'<p>{md_inline(line)}</p>')

        i += 1

    if in_code: out.append('</code></pre>')
    if in_list: out.append('</ul>' if in_list == 'ul' else '</ol>')
    return '\n'.join(out)


def md_inline(text):
    text = escape(text)
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)
    text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    return text


def parse_table(rows):
    if len(rows) < 2:
        return ''
    result = '<div class="table-wrap"><table>\n'
    headers = [h.strip() for h in rows[0].split('|')[1:-1]]
    result += '<thead><tr>' + ''.join(f'<th>{escape(h)}</th>' for h in headers) + '</tr></thead>\n'
    data_rows = rows[2:] if len(rows) > 2 else []
    if data_rows:
        result += '<tbody>\n'
        for row in data_rows:
            cells = [c.strip().replace(':', '').strip() for c in row.split('|')[1:-1]]
            result += '<tr>' + ''.join(f'<td>{md_inline(c)}</td>' for c in cells) + '</tr>\n'
        result += '</tbody>\n'
    result += '</table></div>'
    return result


def split_by_audiencia(body):
    """
    Divide el markdown en secciones por audiencia.
    Retorna: { "intro": "...", "Académico": "...", "Técnico": "...", ... }
    Las secciones se separan por ## con emoji de audiencia (## 🟣, ## 🔵, etc.)
    """
    lines = body.split('\n')
    sections = {"__intro": []}
    current_key = "__intro"

    for line in lines:
        # Detectar encabezado de sección de audiencia
        m = re.match(r'^##\s*([🟣🔵🟢⚪])\s*(.*)', line)
        if m:
            emoji = m.group(1)
            aud = SECTION_MAP.get(emoji)
            if aud:
                current_key = aud
                sections[current_key] = [f"## {m.group(2)}"]  # mantener el heading sin emoji
                continue

        sections.setdefault(current_key, []).append(line)

    # Convertir listas a strings
    result = {}
    for k, v in sections.items():
        result[k] = '\n'.join(v).strip()
    return result


def build_tab_bar(section_keys):
    """Genera la barra de tabs HTML"""
    order = ["Académico", "Técnico", "Profesional", "General"]
    tabs_html = []
    for aud in order:
        if aud in section_keys:
            tag = AUDIENCIA_TAGS[aud]
            tabs_html.append(
                f'<button class="audiencia-tab {tag["cls"]}" '
                f'data-audiencia="{tag["id"]}" '
                f'style="--tab-color:{tag["color"]}">'
                f'{tag["emoji"]} {aud}</button>'
            )
    # Botón "Ver todo"
    tabs_html.append(
        f'<button class="audiencia-tab tab-todos" '
        f'data-audiencia="all">📖 Ver todo</button>'
    )
    return '\n'.join(tabs_html)


def generate_article_html(fm, body, slug):
    title = fm.get('title', 'Sin título')
    series = fm.get('serie', '')
    lectura = fm.get('lectura', '5 min')
    fecha = fm.get('date', datetime.now().strftime('%-d de %B de %Y'))

    # Dividir por audiencia
    sections = split_by_audiencia(body)
    tab_bar = build_tab_bar(sections)

    # Intro (compartida)
    intro_html = ""
    if sections.get("__intro"):
        intro_html = md_to_html(sections["__intro"])

    # Paneles por audiencia
    order = ["Académico", "Técnico", "Profesional", "General"]
    panels_html = ""
    for aud in order:
        if aud in sections:
            tag = AUDIENCIA_TAGS[aud]
            content_html = md_to_html(sections[aud])
            panels_html += f"""
            <div class="audiencia-panel" data-audiencia="{tag["id"]}">
                <div class="panel-label" style="border-left-color:{tag["color"]}">
                    <span class="panel-emoji">{tag["emoji"]}</span>
                    <span>Para {aud.lower()}s</span>
                </div>
                {content_html}
            </div>"""

    # Serie badge
    series_html = ""
    if series:
        series_html = f'<div class="series-badge">📚 Serie: {escape(series)}</div>'

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{escape(title)} — {SITE_NAME}</title>
<meta name="description" content="{SITE_DESC}">
<meta property="og:title" content="{escape(title)}">
<meta property="og:description" content="{SITE_DESC}">
<meta property="og:type" content="article">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:var(--bg-base); color:var(--text); font-family:var(--font-sans); line-height:1.7; -webkit-font-smoothing:antialiased; }}
{DESIGN_TOKENS}

/* ── HEADER ── */
.site-header {{ position:sticky; top:0; z-index:100; background:rgba(7,7,13,0.85); backdrop-filter:blur(12px); border-bottom:1px solid var(--border); }}
.header-inner {{ max-width:1100px; margin:0 auto; padding:0 1.5rem; display:flex; align-items:center; justify-content:space-between; height:64px; }}
.site-logo {{ font-size:1.25rem; font-weight:700; color:var(--text); text-decoration:none; display:flex; align-items:center; gap:0.5rem; }}
.site-logo:hover {{ color:var(--accent); }}
.nav-links {{ display:flex; gap:1.5rem; align-items:center; }}
.nav-links a {{ color:var(--text-muted); text-decoration:none; font-size:0.875rem; font-weight:500; }}
.nav-links a:hover {{ color:var(--text); }}

/* ── ARTICLE ── */
.article-container {{ max-width:var(--max-width); margin:3rem auto; padding:0 1.5rem; }}
.article-header {{ margin-bottom:1.5rem; }}
.article-title {{ font-size:2.25rem; font-weight:800; line-height:1.2; letter-spacing:-0.02em; margin-bottom:0.75rem; color:var(--text); }}
.article-meta {{ display:flex; gap:0.75rem; align-items:center; flex-wrap:wrap; font-size:0.875rem; color:var(--text-muted); }}

.series-badge {{ display:inline-flex; align-items:center; gap:6px; padding:4px 12px; border-radius:var(--radius-sm); font-size:0.75rem; font-weight:500; background:var(--accent-dim); color:var(--accent); border:1px solid rgba(107,207,219,0.2); margin-bottom:0.75rem; }}

/* ── TABS ── */
.audiencia-tabs {{ display:flex; gap:0.5rem; flex-wrap:wrap; margin:1.5rem 0 2rem; padding-bottom:1rem; border-bottom:1px solid var(--border); }}
.audiencia-tab {{ display:inline-flex; align-items:center; gap:4px; padding:6px 14px; border-radius:9999px; font-size:0.8125rem; font-weight:600; cursor:pointer; border:1px solid var(--tab-color); background:transparent; color:var(--tab-color); transition:all 0.15s; font-family:var(--font-sans); }}
.audiencia-tab:hover {{ background:color-mix(in srgb, var(--tab-color) 12%, transparent); }}
.audiencia-tab.active {{ background:var(--tab-color); color:#07070d; }}
.tab-todos {{ --tab-color:var(--text-muted); }}
.tab-todos.active {{ background:var(--text-muted); color:var(--bg-base); }}

/* ── PANELS ── */
.audiencia-panel {{ display:none; }}
.audiencia-panel.active {{ display:block; }}
.panel-label {{ display:flex; align-items:center; gap:8px; padding:8px 12px; margin-bottom:1.5rem; border-left:3px solid; border-radius:0 var(--radius-sm) var(--radius-sm) 0; background:var(--bg-card); font-size:0.8125rem; font-weight:600; color:var(--text-muted); }}
.panel-emoji {{ font-size:1rem; }}

/* ── CONTENT ── */
.article-content {{ font-size:1.0625rem; }}
.article-content h2 {{ font-size:1.5rem; font-weight:700; margin:2.5rem 0 1rem; padding-bottom:0.5rem; border-bottom:1px solid var(--border); color:var(--accent); }}
.article-content h3 {{ font-size:1.25rem; font-weight:600; margin:2rem 0 0.75rem; color:var(--text); }}
.article-content p {{ margin-bottom:1.25rem; color:var(--text-muted); }}
.article-content strong {{ color:var(--text); font-weight:600; }}
.article-content a {{ color:var(--accent); text-decoration:underline; text-underline-offset:2px; }}
.article-content a:hover {{ color:var(--accent-hover); }}
.article-content code {{ font-family:var(--font-mono); font-size:0.875rem; background:var(--bg-card); padding:0.125rem 0.375rem; border-radius:var(--radius-sm); }}
.article-content pre {{ background:var(--bg-card); border-radius:var(--radius); padding:1.25rem; overflow-x:auto; margin:1.5rem 0; border:1px solid var(--border); }}
.article-content pre code {{ background:none; padding:0; font-size:0.8125rem; line-height:1.6; }}
.article-content ul,.article-content ol {{ margin:1rem 0 1.25rem 1.5rem; color:var(--text-muted); }}
.article-content li {{ margin-bottom:0.5rem; }}
.article-content .table-wrap {{ overflow-x:auto; margin:1.5rem 0; border-radius:var(--radius); border:1px solid var(--border); }}
.article-content table {{ width:100%; border-collapse:collapse; font-size:0.875rem; }}
.article-content th {{ background:var(--bg-card); padding:0.75rem 1rem; text-align:left; font-weight:600; color:var(--text); border-bottom:1px solid var(--border); }}
.article-content td {{ padding:0.75rem 1rem; border-bottom:1px solid var(--border); color:var(--text-muted); }}
.article-content tr:last-child td {{ border-bottom:none; }}

/* ── FOOTER ── */
.site-footer {{ border-top:1px solid var(--border); margin-top:4rem; padding:2rem 0; text-align:center; color:var(--text-subtle); font-size:0.8125rem; }}
.site-footer a {{ color:var(--text-muted); text-decoration:none; }}
.site-footer a:hover {{ color:var(--accent); }}
.footer-inner {{ max-width:var(--max-width); margin:0 auto; padding:0 1.5rem; }}

@media (max-width:640px) {{ .article-title {{ font-size:1.75rem; }} .audiencia-tabs {{ gap:0.375rem; }} .audiencia-tab {{ font-size:0.75rem; padding:5px 10px; }} }}
</style>
</head>
<body>
<header class="site-header">
<div class="header-inner">
<a href="/" class="site-logo">⟨ PADIM ⟩</a>
<nav class="nav-links">
<a href="/">Blog</a>
<a href="http://padim.enmexico.casa:8081">Protocolo</a>
</nav>
</div>
</header>

<article class="article-container">
<header class="article-header">
{series_html}
<h1 class="article-title">{escape(title)}</h1>
<div class="article-meta"><span>{fecha}</span><span> · </span><span>{lectura}</span></div>
</header>

<div class="article-intro">{intro_html}</div>

<div class="audiencia-tabs" role="tablist">{tab_bar}</div>

{panels_html}

</article>

<footer class="site-footer">
<div class="footer-inner">
<p><a href="http://padim.enmexico.casa:8081">PADIM</a> — Protocolo Abierto de Datos Inmobiliarios de México</p>
<p style="margin-top:0.25rem">El protocolo es de todos. El protocolo es de nadie.</p>
</div>
</footer>

<script>
(function(){{
    const tabs = document.querySelectorAll('.audiencia-tab');
    const panels = document.querySelectorAll('.audiencia-panel');
    if (!tabs.length) return;

    function getInitialTab() {{
        const hash = window.location.hash.replace('#','');
        if (hash) {{
            for (const t of tabs)
                if (t.dataset.audiencia === hash) return hash;
        }}
        return localStorage.getItem('padim-audiencia') || 'all';
    }}

    function switchTab(id) {{
        tabs.forEach(t => t.classList.toggle('active', t.dataset.audiencia === id));
        panels.forEach(p => p.classList.toggle('active', p.dataset.audiencia === id));
        try {{ localStorage.setItem('padim-audiencia', id); }} catch(e) {{}}
        const url = id === 'all' ? window.location.pathname : '#' + id;
        history.replaceState(null, '', url);
    }}

    tabs.forEach(t => t.addEventListener('click', () => switchTab(t.dataset.audiencia)));

    const initial = getInitialTab();
    if (initial && initial !== 'all') switchTab(initial);
    else {{
        tabs.forEach(t => t.classList.toggle('active', t.dataset.audiencia === 'all'));
        panels.forEach(p => p.classList.add('active'));
    }}

    window.addEventListener('hashchange', () => {{
        const id = window.location.hash.replace('#','');
        if (id && document.querySelector(`[data-audiencia="${{id}}"]`)) switchTab(id);
    }});
}})();
</script>
</body>
</html>"""


def generate_home_html(posts):
    cards = ""
    for slug, fm, _ in posts[:12]:
        aud = fm.get('audiencia', ['General'])
        if isinstance(aud, str):
            aud = [aud]
        badges = []
        for a in aud:
            tag = AUDIENCIA_TAGS.get(a)
            if tag:
                badges.append(
                    f'<span class="tag-audiencia {tag["cls"]}" '
                    f'style="--tag-color:{tag["color"]}">{tag["emoji"]}</span>'
                )
        badges_html = ' '.join(badges)
        fecha = fm.get('date', '')
        title_s = fm.get('title', '')
        desc = fm.get('description', '')
        cards += f"""
        <a href="/posts/{slug}/" class="post-card">
            <div class="post-card-meta">{badges_html}<span class="post-card-date">{fecha}</span></div>
            <h2 class="post-card-title">{escape(title_s)}</h2>
            <p class="post-card-desc">{escape(desc)[:150]}{'…' if len(desc)>150 else ''}</p>
        </a>"""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{SITE_NAME} — {SITE_DESC}</title>
<meta name="description" content="{SITE_DESC}">
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:var(--bg-base); color:var(--text); font-family:var(--font-sans); line-height:1.7; }}
{DESIGN_TOKENS}
.site-header {{ position:sticky; top:0; z-index:100; background:rgba(7,7,13,0.85); backdrop-filter:blur(12px); border-bottom:1px solid var(--border); }}
.header-inner {{ max-width:1100px; margin:0 auto; padding:0 1.5rem; display:flex; align-items:center; justify-content:space-between; height:64px; }}
.site-logo {{ font-size:1.25rem; font-weight:700; color:var(--text); text-decoration:none; }}
.nav-links {{ display:flex; gap:1.5rem; }}
.nav-links a {{ color:var(--text-muted); text-decoration:none; font-size:0.875rem; font-weight:500; }}
.nav-links a:hover {{ color:var(--text); }}
.hero {{ text-align:center; padding:5rem 1.5rem 3rem; max-width:700px; margin:0 auto; }}
.hero h1 {{ font-size:2.75rem; font-weight:800; letter-spacing:-0.03em; line-height:1.15; margin-bottom:1rem; color:var(--text); }}
.hero h1 span {{ color:var(--accent); }}
.hero p {{ font-size:1.125rem; color:var(--text-muted); max-width:560px; margin:0 auto; }}
.posts-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(320px,1fr)); gap:1.5rem; max-width:1100px; margin:0 auto; padding:0 1.5rem 4rem; }}
.post-card {{ background:var(--bg-card); border-radius:var(--radius); padding:1.5rem; border:1px solid var(--border); text-decoration:none; color:inherit; transition:all 0.2s; display:flex; flex-direction:column; gap:0.75rem; }}
.post-card:hover {{ background:var(--bg-card-hover); border-color:var(--border-hover); transform:translateY(-2px); }}
.post-card-meta {{ display:flex; gap:0.5rem; align-items:center; flex-wrap:wrap; }}
.post-card-date {{ font-size:0.75rem; color:var(--text-subtle); }}
.post-card-title {{ font-size:1.125rem; font-weight:600; line-height:1.3; }}
.post-card-desc {{ font-size:0.875rem; color:var(--text-muted); line-height:1.5; }}
.tag-audiencia {{ display:inline-flex; align-items:center; justify-content:center; width:22px; height:22px; border-radius:50%; font-size:0.7rem; border:1px solid var(--tag-color); background:rgba(0,0,0,0.3); }}
.site-footer {{ border-top:1px solid var(--border); padding:2rem 0; text-align:center; color:var(--text-subtle); font-size:0.8125rem; }}
.site-footer a {{ color:var(--text-muted); text-decoration:none; }}
.site-footer a:hover {{ color:var(--accent); }}
@media (max-width:640px) {{ .hero h1 {{ font-size:2rem; }} .hero {{ padding:3rem 1rem 2rem; }} .posts-grid {{ grid-template-columns:1fr; }} }}
</style>
</head>
<body>
<header class="site-header">
<div class="header-inner">
<a href="/" class="site-logo">⟨ PADIM ⟩ Blog</a>
<nav class="nav-links"><a href="http://padim.enmexico.casa:8081">Protocolo</a></nav>
</div>
</header>
<section class="hero">
<h1>Datos que <span>transforman</span> el mercado inmobiliario</h1>
<p>Exploramos el futuro de los datos abiertos, la transparencia y la tecnología en el sector inmobiliario mexicano.</p>
</section>
<div class="posts-grid">{cards}</div>
<footer class="site-footer">
<div class="footer-inner">
<p><a href="http://padim.enmexico.casa:8081">PADIM</a> — Protocolo Abierto de Datos Inmobiliarios de México</p>
</div>
</footer>
</body>
</html>"""


def main():
    posts = []
    for post_dir in sorted(POSTS_DIR.iterdir()):
        if post_dir.is_dir():
            md_file = post_dir / "index.md"
            if md_file.exists():
                text = md_file.read_text(encoding='utf-8')
                fm, body = parse_frontmatter(text)
                slug = post_dir.name
                posts.append((slug, fm, body))

    posts.sort(key=lambda x: x[1].get('date', ''), reverse=True)

    if not posts:
        print("⚠️ No se encontraron artículos")
        return

    for slug, fm, body in posts:
        html = generate_article_html(fm, body, slug)
        post_out = OUTPUT_DIR / "posts" / slug
        post_out.mkdir(parents=True, exist_ok=True)
        (post_out / "index.html").write_text(html, encoding='utf-8')
        print(f"✅ posts/{slug}/index.html")

    home_html = generate_home_html(posts)
    (OUTPUT_DIR / "index.html").write_text(home_html, encoding='utf-8')
    print("✅ index.html (home)")
    print(f"\n📊 {len(posts)} artículo(s) — {OUTPUT_DIR}")


if __name__ == "__main__":
    main()