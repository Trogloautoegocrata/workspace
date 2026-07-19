#!/usr/bin/env python3
"""Extrae párrafos de un post HTML a un txt para análisis."""
import re
import sys
from pathlib import Path

def extract(input_path, output_path):
    html = Path(input_path).read_text(encoding='utf-8')

    body_start = html.find('<body>')
    body_end = html.find('</body>')

    # Buscar <div class="post-content" ...>
    content_match = re.search(r'<(div class="post-content"[^>]*)>', html[body_start:body_end])
    if not content_match:
        # Buscar el primer <article>
        content_match = re.search(r'<(article[^>]*)>', html[body_start:body_end])

    if not content_match:
        print('No se encontró post-content ni article')
        return

    start = body_start + content_match.end()
    end_marker = html.find('<div class="author-bio"', start)
    if end_marker == -1:
        end_marker = html.find('</article>', start)
    end = html.rfind('</div>', start, end_marker) if end_marker > 0 else body_end

    body = html[start:end]
    paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', body, re.DOTALL)

    with open(output_path, 'w', encoding='utf-8') as f:
        for i, p in enumerate(paragraphs):
            clean = re.sub(r'<[^>]+>', ' ', p).strip()
            clean = re.sub(r'\s+', ' ', clean)
            f.write(f'[P{i:03d}] ({len(clean):4d}c) {clean[:300]}\n')

    print(f'Wrote {len(paragraphs)} paragraphs to {output_path}')

if __name__ == '__main__':
    extract(sys.argv[1], sys.argv[2])
