#!/bin/bash
# Caddy Workspace Watchdog
# Verifica que workspace.visionnorth.mx apunte al puerto correcto del workspace server
# Se ejecuta cada hora cron para prevenir desajustes tras reinicios/actualizaciones
#
# Histórico:
#   - Antes apuntaba a :7700 (Meilisearch por error de configuración)
#   - Ahora apunta a :7701 (servidor de archivos workspace_visionnorth, Python SimpleHTTP)

CADDYFILE="/home/polaris/workspace/.caddy-temp/Caddyfile"
DOMAIN="workspace.visionnorth.mx"
EXPECTED_PORT="7701"
STATE_FILE="/tmp/caddy-workspace-watchdog.last"

# Leer el puerto actual del Caddyfile para el dominio
CURRENT_PORT=$(grep -A5 "^\s*${DOMAIN}\s*{" "$CADDYFILE" 2>/dev/null | grep "reverse_proxy" | grep -oP 'localhost:\K[0-9]+')

if [ -z "$CURRENT_PORT" ]; then
    echo "[$(date)] WARNING: No se encontró reverse_proxy para $DOMAIN en $CADDYFILE"
    exit 1
fi

if [ "$CURRENT_PORT" != "$EXPECTED_PORT" ]; then
    echo "[$(date)] CORRIGIENDO: $DOMAIN apuntaba a :$CURRENT_PORT → :$EXPECTED_PORT"
    # No podemos hacer sed sin sudo, así que reportamos
    echo "ACTION_NEEDED:sudo sed -i 's/reverse_proxy localhost:${CURRENT_PORT}/reverse_proxy localhost:${EXPECTED_PORT}/' $CADDYFILE && sudo caddy reload --config $CADDYFILE"
    exit 2
fi

echo "[$(date)] OK: $DOMAIN → localhost:$EXPECTED_PORT ✓"
exit 0
