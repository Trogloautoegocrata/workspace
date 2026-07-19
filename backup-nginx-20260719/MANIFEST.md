# Respaldo Nginx — 2026-07-19T09:37:40Z

## Propósito
Respaldo completo de configuraciones de nginx antes de corregir
el catch-all en puerto 443 causado por admin-nexus.

## Archivos
- `sites-available/` — Configs originales de cada site
- `sites-enabled/` — Symlinks activos
- `nginx-config/` — nginx.conf principal
- `caddy/` — Configs de Caddy (incluye blog-padim.conf)
- `dns-status.txt` — Resolución DNS de dominios clave

## Estado actual (pre-fix)
- admin-nexus es el default implícito en puerto 443
- blog.enmexico.casa HTTPS → Approval Gate
- nexus.christmas HTTPS → Approval Gate
