#!/usr/bin/env python3
"""Elimina footers duplicados en los posts del blog. Solo deja el footer DENTRO de <article>."""
import re

paths = [
    '/home/polaris/workspace/public/blog-polaris/posts/cuanto-cuesta-una-pagina-web-guia-actualizada-2025/index.html',
    '/home/polaris/workspace/public/blog-polaris/posts/entendiendo-la-encuesta-para-desarrolladores-de-stack-overflow-2025/index.html',
]

for path in paths:
    with open(path) as f:
        html = f.read()

    # Encontrar TODOS los footers
    footer_pattern = re.compile(
        r'\n    <footer class="site-footer">.*?</footer>\n',
        re.DOTALL
    )
    matches = list(footer_pattern.finditer(html))
    print(f'{path}: {len(matches)} footers encontrados')

    if len(matches) > 1:
        # Eliminar todos menos el último
        # Iterar de atrás hacia adelante
        for m in reversed(matches[:-1]):
            html = html[:m.start()] + html[m.end():]
            print(f'  Eliminado footer en posición {m.start()}')

        with open(path, 'w') as f:
            f.write(html)
        print(f'  Guardado')
    elif len(matches) == 1:
        print(f'  Solo hay 1 footer (OK)')
