#!/bin/bash
# Aplicar fixes al Caddyfile (v5 - redir con rewrite)
# Uso: sudo /home/polaris/workspace/scripts/apply-caddy-fix.sh

set -e

CADDYFILE="/etc/caddy/Caddyfile"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP="${CADDYFILE}.backup.${TIMESTAMP}.cleanup-fix"

cp "$CADDYFILE" "$BACKUP"
echo "✅ Backup: $BACKUP"

sed -i '/^back-bone.dev {$/,/^}$/c\
back-bone.dev {\
    root * \/home\/polaris\/workspace\/projects\/BACKBONE\/frontend\
    encode gzip zstd\
\
    # Privacy: ruta sin extension sirve privacy.html\
    handle \/privacy {\
        rewrite \/privacy.html\
        file_server\
    }\
    handle \/terms {\
        rewrite \/terms.html\
        file_server\
    }\
\
    # Catch-all SPA para el router client-side\
    handle {\
        try_files {path} \/index.html\
        file_server\
    }\
}' "$CADDYFILE"

# Cleanup
sed -i '/^flow.visionnorth.mx {$/,/^}$/d' "$CADDYFILE"
sed -i '/^academia.visionnorth.mx {$/,/^}$/d' "$CADDYFILE"

echo "✅ Cambios aplicados"
echo "--- Validando Caddyfile ---"
caddy validate --config "$CADDYFILE" 2>&1
echo "--- Recargando Caddy ---"
caddy reload --config "$CADDYFILE" 2>&1
echo "✅ Fix completado"
