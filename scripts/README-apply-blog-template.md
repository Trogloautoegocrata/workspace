# apply_blog_template.py

Script único para mantener la **consistencia visual** del blog y glosario Polaris.

## ¿Qué hace?

Aplica la **plantilla maestra** (logo canónico + footer inline) a TODOS los HTMLs del blog
y glosario en una sola ejecución. Reemplaza el flujo anterior donde había que arreglar
cada artículo individualmente.

## Problemas que resuelve

| Antes | Ahora |
|---|---|
| Logo inconsistente entre artículos (estrella vs logo completo) | Logo canónico en todos |
| Footer se inyectaba via JS (no aparecía en `file://`, scrapers, sin JS) | Footer inline en HTML |
| Fix puntual artículo por artículo | 1 comando, 4 HTMLs arreglados |
| Logo en paths diferentes (`/LOGO-POLARIS.png` vs `/assets/polaris-logo.png`) | Path canónico `/assets/polaris-logo.png` |

## Uso

```bash
# Ver qué cambiaría (sin tocar archivos)
python3 apply_blog_template.py --dry-run

# Aplicar a todos los HTMLs
python3 apply_blog_template.py

# Aplicar a un solo archivo
python3 apply_blog_template.py --path /path/al/archivo.html

# Ver cada cambio
python3 apply_blog_template.py --verbose
```

## Sitios que procesa

- `public/blog-polaris/` (3 HTMLs: home + 2 artículos)
- `public/glosario-polaris-v1.0.2/` (1 HTML: home)

Total: 4 HTMLs

## Idempotencia

El script es **idempotente**: ejecutarlo varias veces no duplica nada. Si el HTML ya
tiene el footer `pol-tail-final` y el logo canónico, no hace nada.

## Configuración (al inicio del script)

```python
SITES = [
    Path('/home/polaris/workspace/public/blog-polaris'),
    Path('/home/polaris/workspace/public/glosario-polaris-v1.0.2'),
]
```

## Rollback

Los logos viejos están respaldados como `.old`:
- `public/blog-polaris/LOGO-POLARIS.png.old`
- `public/blog-polaris/assets/polaris-logo.png.old`

Para rollback manual:
```bash
mv public/blog-polaris/LOGO-POLARIS.png.old public/blog-polaris/LOGO-POLARIS.png
mv public/blog-polaris/assets/polaris-logo.png.old public/blog-polaris/assets/polaris-logo.png
```

## Cambios futuros

Si necesitas cambiar el logo, el footer, o el header:

1. Edita los bloques al inicio del script (`LOGO_IMG`, `HEADER_BLOCK`, `FOOTER_BLOCK`)
2. Corre `python3 apply_blog_template.py` 
3. Listo — todos los HTMLs quedan consistentes

**No** edites los HTMLs individuales.
