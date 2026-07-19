#!/usr/bin/env python3
"""
Solución al problema de Cloudflare Email Protection que rompe el footer.

Cloudflare inyecta widgets al final del HTML que desplazan/eliminan
el contenido del footer. La solución: renderizar el footer via JS
en el lado del cliente, después de que Cloudflare ya terminó su trabajo.
"""
import re

paths = [
    '/home/polaris/workspace/public/blog-polaris/posts/cuanto-cuesta-una-pagina-web-guia-actualizada-2025/index.html',
    '/home/polaris/workspace/public/blog-polaris/posts/entendiendo-la-encuesta-para-desarrolladores-de-stack-overflow-2025/index.html',
]

# Código que se inyecta al final de cada post para crear el footer via JS
FOOTER_INJECTION = '''
    <!-- Footer inyectado via JS para evitar interferencia de Cloudflare Email Protection -->
    <div id="post-footer-slot"></div>
    <script>
    (function() {
        var slot = document.getElementById('post-footer-slot');
        if (!slot) return;
        var footer = document.createElement('footer');
        footer.className = 'site-footer';
        footer.innerHTML = '<div class="footer-inner">' +
            '<div class="footer-links">' +
            '<a href="/">Blog</a>' +
            '<a href="https://glosario.polaris.pw/glossary/">Glosario</a>' +
            '</div>' +
            '<p>&copy; 2025 <a href="https://blog.polaris.pw">Polaris</a>. Editorial v2.0 &mdash; todos los derechos reservados.</p>' +
            '</div>';
        // Insertar en el lugar del slot
        slot.parentNode.insertBefore(footer, slot);
        slot.parentNode.removeChild(slot);
    })();
    </script>
'''

for path in paths:
    with open(path) as f:
        html = f.read()

    # 1. Eliminar cualquier footer existente
    footer_pattern = re.compile(r'\n        <footer class="site-footer">.*?</footer>\n', re.DOTALL)
    html_new = footer_pattern.sub('', html)

    # 2. Eliminar scripts de reading progress (no necesarios)
    # NO - los dejamos

    # 3. Inyectar antes de </body>
    if '</body>' in html_new and 'post-footer-slot' not in html_new:
        html_new = html_new.replace('</body>', FOOTER_INJECTION + '\n</body>', 1)
        with open(path, 'w') as f:
            f.write(html_new)
        print(f'OK: {path}')
    else:
        print(f'SKIP (ya inyectado o sin </body>): {path}')
