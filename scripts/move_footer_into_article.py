#!/usr/bin/env python3
"""Mueve el footer del post para que esté DENTRO de <article> (no después de </main>)."""
import re
import sys

paths = [
    '/home/polaris/workspace/public/blog-polaris/posts/cuanto-cuesta-una-pagina-web-guia-actualizada-2025/index.html',
    '/home/polaris/workspace/public/blog-polaris/posts/entendiendo-la-encuesta-para-desarrolladores-de-stack-overflow-2025/index.html',
]

for path in paths:
    with open(path) as f:
        html = f.read()

    # Extraer el bloque del footer
    m = re.search(r'(    <footer class="site-footer">.*?</footer>\n\n)', html, re.DOTALL)
    if not m:
        print(f'No footer en {path}')
        continue
    footer = m.group(1)
    print(f'Footer extraído: {len(footer)} bytes')

    # Quitar el footer de su posición actual
    html = html.replace(footer, '', 1)

    # Insertar antes de </article>
    if '</article>' in html:
        html = html.replace('</article>', footer + '    </article>', 1)
    else:
        print(f'No </article> en {path}')

    with open(path, 'w') as f:
        f.write(html)
    print(f'Guardado: {path}')

print('Done')
