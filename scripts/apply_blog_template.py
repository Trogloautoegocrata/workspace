#!/usr/bin/env python3
"""
apply_blog_template.py — Aplica la plantilla maestra del blog/glosario a todos los HTMLs.

Solución a 3 problemas que estaban arreglándose artículo por artículo:
1. Logo inconsistente (estrella vs logo completo) — ahora se reemplaza por el logo canónico
2. Footer inexistente (script JS no se ejecuta en file://, Cloudflare, scrapers) — ahora va inline
3. Inconsistencia de paths de logo entre artículos — ahora se normaliza a /assets/polaris-logo.png

USO:
    python3 apply_blog_template.py                 # procesa todos los HTMLs
    python3 apply_blog_template.py --dry-run       # muestra qué cambiaría sin tocar
    python3 apply_blog_template.py --path FILE     # procesa un solo archivo
    python3 apply_blog_template.py --verbose       # muestra cada cambio

El script es IDEMPOTENTE: ejecutarlo varias veces no duplica nada.
"""
import re
import sys
import argparse
from pathlib import Path

# === CONFIGURACIÓN ===

# Rutas raíz del blog y glosario (versiones activas en PRODUCCIÓN)
# glosario-polaris/ es el que sirve glosario.polaris.pw (md5 match verificado)
# glosario-polaris-v1.0.2/ es la versión de desarrollo local (no se sirve online)
SITES = [
    Path('/home/polaris/workspace/public/blog-polaris'),
    Path('/home/polaris/workspace/public/glosario-polaris'),
    Path('/home/polaris/workspace/public/glosario-polaris-v1.0.2'),
]

# Cache-busting para el logo: forzar recarga en Cloudflare cache (HIT → MISS)
# Cloudflare cachea por URL completa, así que ?v=2 es una URL nueva
LOGO_CACHE_BUST = '?v=2'

# Paths de logo (orden de preferencia: el nuevo logo canónico)
CANONICAL_LOGO_SRC = '/assets/polaris-logo.png'   # path relativo limpio
LEGACY_LOGO_PATHS = [
    '/LOGO-POLARIS.png',
    '/assets/polaris-logo.png',   # también se normaliza al mismo para consistencia
]

# === FRAGMENTOS DE PLANTILLA ===

# Bloque <img> del logo — tamaño consistente, inline style para no depender de CSS externo
# Logo horizontal 934x245, ratio 3.81:1 → height:44px → width:168px
# Cache-busting (?v=2) para forzar recarga en Cloudflare
LOGO_IMG = (
    f'<img src="/assets/polaris-logo.png{LOGO_CACHE_BUST}" alt="Polaris" '
    'style="height:44px;width:auto;max-width:180px;display:block;" '
    'loading="eager" decoding="async">'
)

# Regex para encontrar cualquier <img> que apunte a un logo viejo o al nuevo
# Captura el tag <a> que envuelve el logo (hasta el cierre </a>)
LOGO_LINK_RE = re.compile(
    r'<a\s+href="(?:/|https://blog\.polaris\.pw/?)"[^>]*class="site-logo"[^>]*>.*?</a>',
    re.DOTALL | re.IGNORECASE,
)

# Bloque <header> con el logo nuevo — reemplaza cualquier header.site-header existente
HEADER_BLOCK = '''<header class="site-header" style="border-bottom:1px solid #1e1e2e;padding:14px 0;position:sticky;top:0;z-index:100;background:rgba(10,10,15,0.92);backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);">
    <div class="header-inner" style="display:flex;align-items:center;justify-content:space-between;max-width:1120px;margin:0 auto;padding:0 24px;">
        <a href="/" class="site-logo" aria-label="Polaris" style="display:flex;align-items:center;gap:10px;font-size:1.25rem;font-weight:800;color:#e5e5e9;letter-spacing:-0.02em;text-decoration:none;transition:opacity 0.25s;">
            {LOGO_IMG}
        </a>
        <nav class="nav-links" style="display:flex;gap:28px;align-items:center;">
            <a href="/" style="color:#8888a0;text-decoration:none;font-weight:500;transition:color 0.25s;">Blog</a>
            <a href="https://glosario.polaris.pw/glossary/" style="color:#8888a0;text-decoration:none;font-weight:500;transition:color 0.25s;">Glosario</a>
        </nav>
    </div>
</header>'''

# Footer INLINE — funciona sin JS, sin Cloudflare, sin file://
FOOTER_BLOCK = '''<footer class="site-footer pol-tail-final" role="contentinfo" style="margin-top:80px;padding:48px 24px 32px;border-top:1px solid #1e1e2e;background:#0a0a0f;text-align:center;">
    <div class="pol-tail-inner" style="max-width:1120px;margin:0 auto;">
        <div class="pol-tail-links" style="display:flex;gap:24px;flex-wrap:wrap;justify-content:center;margin-bottom:16px;">
            <a href="/" style="color:#1edb7f;text-decoration:none;font-weight:500;transition:color 0.25s;">Blog</a>
            <a href="https://glosario.polaris.pw/glossary/" style="color:#1edb7f;text-decoration:none;font-weight:500;transition:color 0.25s;">Glosario</a>
            <a href="https://polaris.pw" style="color:#1edb7f;text-decoration:none;font-weight:500;transition:color 0.25s;">Polaris by VisionNorth</a>
        </div>
        <p style="color:#5a5a66;font-size:0.875rem;margin:0;">&copy; 2025 <a href="https://blog.polaris.pw" style="color:#1edb7f;text-decoration:none;">Polaris</a>. Editorial v2.0 &mdash; todos los derechos reservados.</p>
    </div>
</footer>'''


def find_html_files(sites):
    """Encuentra todos los HTMLs en los sitios dados, excluyendo backups."""
    files = []
    for site in sites:
        if not site.exists():
            print(f"  ⚠️  Sitio no existe: {site}", file=sys.stderr)
            continue
        for html in site.rglob('*.html'):
            # Excluir backups
            if '.old' in html.name or 'backup' in html.name:
                continue
            files.append(html)
    return files


def process_html(html_path, dry_run=False, verbose=False):
    """
    Aplica la plantilla a un HTML.
    Retorna (cambios_aplicados, descripción_cambios).
    """
    try:
        content = html_path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        try:
            content = html_path.read_text(encoding='latin-1')
        except Exception as e:
            return False, f"Error leyendo: {e}"

    original = content
    changes = []

    # === 1. Reemplazar logo viejo por nuevo ===
    # Patrones comunes del logo viejo (estrella) y actuales (sin cache-busting)
    old_logo_patterns = [
        r'<img\s+src="/LOGO-POLARIS\.png"[^>]*>',
        r'<img\s+src="/assets/polaris-logo\.png(?:\?v=\d+)?"[^>]*>',
        r'<img\s+src="https://blog\.polaris\.pw/[^"]*logo[^"]*"[^>]*>',
        # SVG de estrella dorada
        r'<svg[^>]*class="logo-star"[^>]*>.*?</svg>',
    ]
    for pattern in old_logo_patterns:
        matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
        if matches:
            content = re.sub(pattern, LOGO_IMG, content, flags=re.DOTALL | re.IGNORECASE)
            changes.append(f"logo ({len(matches)} instancias)")

    # === 2. Reemplazar el <a class="site-logo"> que envuelve el logo ===
    # Esto asegura que el contenedor <a> también tenga la estructura correcta
    new_a_with_logo = (
        '<a href="/" class="site-logo" aria-label="Polaris" '
        'style="display:flex;align-items:center;gap:10px;text-decoration:none;transition:opacity 0.25s;">'
        f'{LOGO_IMG}</a>'
    )
    if LOGO_LINK_RE.search(content):
        content = LOGO_LINK_RE.sub(new_a_with_logo, content)
        # Solo contar si había logo referenciado antes
        if 'site-logo' in original and 'site-logo' in content:
            # Verificar que cambió
            if new_a_with_logo in content and new_a_with_logo not in original:
                changes.append("link de logo")

    # === 3. Inyectar, REEMPLAZAR o DEDUPLICAR footer inline ===
    # Tres casos:
    # A. Sin footer: inyectar
    # B. Footer único que NO es el canónico: REEMPLAZAR con canónico
    # C. Footer único canónico: OK (verificar posición)
    # D. Múltiples footers: eliminar los que NO son canónicos (duplicación)
    footer_marker = 'pol-tail-final'
    has_canonical_footer = footer_marker in content

    # Buscar TODOS los footers
    all_footers = list(re.finditer(r'<footer[^>]*>.*?</footer>', content, re.DOTALL))

    if len(all_footers) > 1:
        # DUPLICACIÓN: hay múltiples footers. Eliminar los que NO son canónicos.
        # Mantener solo el canónico (con pol-tail-final)
        # Si no hay canónico, mantener el último y eliminar los demás
        canonical = None
        non_canonical = []
        for m in all_footers:
            if footer_marker in m.group(0):
                canonical = m
            else:
                non_canonical.append(m)

        if not canonical:
            # No hay canónico, usar el último como canónico (después lo reemplazamos)
            canonical = all_footers[-1]
            non_canonical = all_footers[:-1]

        # Eliminar todos los no-canónicos (en orden inverso para no afectar índices)
        for m in sorted(non_canonical, key=lambda x: x.start(), reverse=True):
            content = content[:m.start()] + content[m.end():]
        changes.append(f"eliminados {len(non_canonical)} footers duplicados")

        # Si el canónico que queda NO es el nuestro, reemplazarlo
        if footer_marker not in (canonical.group(0) if canonical else ''):
            # Eliminar el canónico actual
            if canonical:
                content = content[:canonical.start()] + content[canonical.end():]
            # Inyectar el nuestro en posición correcta
            main_close = content.rfind('</main>')
            body_close = content.rfind('</body>')
            if main_close > 0 and main_close < body_close:
                content = content.replace('</main>', '</main>\n\n    ' + FOOTER_BLOCK, 1)
                changes.append("footer canónico inyectado (después de </main>)")
            elif body_close > 0:
                content = content.replace('</body>', FOOTER_BLOCK + '\n\n</body>', 1)
                changes.append("footer canónico inyectado (antes de </body>)")
    elif len(all_footers) == 1:
        # Footer único
        footer = all_footers[0]
        if footer_marker not in footer.group(0):
            # No es canónico. Reemplazarlo.
            content = content[:footer.start()] + content[footer.end():]
            main_close = content.rfind('</main>')
            body_close = content.rfind('</body>')
            if main_close > 0 and main_close < body_close:
                content = content.replace('</main>', '</main>\n\n    ' + FOOTER_BLOCK, 1)
                changes.append("footer original reemplazado (después de </main>)")
            elif body_close > 0:
                content = content.replace('</body>', FOOTER_BLOCK + '\n\n</body>', 1)
                changes.append("footer original reemplazado (antes de </body>)")
        else:
            # Es canónico. Verificar posición.
            footer_pos = content.find('pol-tail-final')
            main_close_pos = content.rfind('</main>')
            if main_close_pos > 0 and footer_pos < main_close_pos:
                # Está mal posicionado
                footer_match = re.search(
                    r'\n    <footer class="site-footer pol-tail-final".*?</footer>\n    ',
                    content, re.DOTALL
                )
                if footer_match:
                    content = content[:footer_match.start()] + content[footer_match.end():]
                    new_main_close = content.rfind('</main>')
                    if new_main_close > 0:
                        content = content[:new_main_close] + '</main>\n\n    ' + FOOTER_BLOCK + content[new_main_close+len('</main>'):]
                    else:
                        content = content.replace('</body>', FOOTER_BLOCK + '\n\n</body>', 1)
                    changes.append("footer reubicado (fuera de article/main)")
    else:
        # Sin footer. Inyectar.
        main_close = content.rfind('</main>')
        body_close = content.rfind('</body>')
        if main_close > 0 and main_close < body_close:
            content = content.replace('</main>', '</main>\n\n    ' + FOOTER_BLOCK, 1)
            changes.append("footer nuevo (después de </main>)")
        elif '<script src="/pol-tail.js' in content:
            content = re.sub(
                r'\s*<script src="/pol-tail\.js[^"]*"></script>\s*',
                '\n    ' + FOOTER_BLOCK + '\n    ',
                content, count=1
            )
            changes.append("footer nuevo (JS → inline)")
        elif body_close > 0:
            content = content.replace('</body>', '\n    ' + FOOTER_BLOCK + '\n\n</body>', 1)
            changes.append("footer nuevo (inline)")

    # === 4. Eliminar <script src="/pol-tail.js"> si todavía existe (footer ya es inline) ===
    content = re.sub(
        r'\s*<script src="/pol-tail\.js[^"]*"></script>\s*',
        '\n    ',
        content
    )
    if '<script src="/pol-tail.js' in original and '<script src="/pol-tail.js' not in content:
        changes.append("pol-tail.js removido")

    # === Guardar solo si hubo cambios ===
    if content != original and not dry_run:
        html_path.write_text(content, encoding='utf-8')
        return True, ', '.join(changes)
    elif content != original and dry_run:
        return True, f"[DRY-RUN] {', '.join(changes)}"
    else:
        return False, "sin cambios"


def main():
    parser = argparse.ArgumentParser(
        description='Aplica la plantilla maestra (logo + footer) al blog y glosario.'
    )
    parser.add_argument('--dry-run', action='store_true', help='No modifica archivos')
    parser.add_argument('--verbose', action='store_true', help='Muestra cada cambio')
    parser.add_argument('--path', type=Path, help='Procesa un solo archivo')
    args = parser.parse_args()

    print("=" * 60)
    print("APPLY BLOG TEMPLATE — Logo canónico + footer inline")
    print("=" * 60)
    print()

    if args.path:
        files = [args.path]
        print(f"Modo: archivo único → {args.path}")
    else:
        files = find_html_files(SITES)
        print(f"Modo: batch ({len(files)} HTMLs encontrados)")
        for site in SITES:
            n = sum(1 for f in files if str(f).startswith(str(site)))
            print(f"  • {site.name}: {n} HTMLs")

    print()
    if args.dry_run:
        print("⚠️  DRY-RUN: no se modificarán archivos")
        print()

    modified = 0
    skipped = 0
    errors = 0

    for html_path in sorted(files):
        if not html_path.exists():
            print(f"  ✗ No existe: {html_path}", file=sys.stderr)
            errors += 1
            continue

        ok, desc = process_html(html_path, dry_run=args.dry_run, verbose=args.verbose)

        if ok:
            modified += 1
            marker = '🟢' if not args.dry_run else '🔍'
            print(f"  {marker} {html_path.relative_to(html_path.parents[2])}: {desc}")
        else:
            skipped += 1
            if args.verbose and desc != "sin cambios":
                print(f"  ⚪ {html_path}: {desc}")

    print()
    print("=" * 60)
    print(f"Resultado: {modified} modificados, {skipped} sin cambios, {errors} errores")
    if args.dry_run:
        print("⚠️  DRY-RUN: ejecuta sin --dry-run para aplicar los cambios")
    print("=" * 60)

    return 0 if errors == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
