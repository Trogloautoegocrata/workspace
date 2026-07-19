#!/bin/bash
# backup-nginx.sh — Respaldar configs de nginx antes de modificarlas
# Ejecutar con: bash scripts/backup-nginx.sh
# Si no tienes sudo, ejecutar: sudo bash scripts/backup-nginx.sh

BACKUP_DIR="/home/polaris/workspace/backup-nginx-20260719"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

echo "📦 Respaldo Nginx — $TIMESTAMP"
echo "Destino: $BACKUP_DIR"
echo ""

# Crear estructura
mkdir -p "$BACKUP_DIR/sites-available"
mkdir -p "$BACKUP_DIR/sites-enabled"
mkdir -p "$BACKUP_DIR/nginx-config"
mkdir -p "$BACKUP_DIR/caddy"

# 1. Sites-available (root:600 — necesita sudo)
echo "1. Copiando /etc/nginx/sites-available/ ..."
for f in /etc/nginx/sites-available/*; do
    name=$(basename "$f")
    cp "$f" "$BACKUP_DIR/sites-available/$name" 2>/dev/null && \
        echo "   ✅ $name ($(wc -c < "$f") bytes)" || \
        echo "   ❌ $name (sin permisos)"
done

# 2. Sites-enabled (symlinks)
echo ""
echo "2. Copiando /etc/nginx/sites-enabled/ ..."
for f in /etc/nginx/sites-enabled/*; do
    name=$(basename "$f")
    if [ -L "$f" ]; then
        target=$(readlink "$f")
        echo "LINK -> $target" > "$BACKUP_DIR/sites-enabled/$name"
        echo "   🔗 $name -> $target"
    else
        cp "$f" "$BACKUP_DIR/sites-enabled/$name" && \
            echo "   ✅ $name"
    fi
done

# 3. nginx.conf principal
echo ""
echo "3. Copiando /etc/nginx/nginx.conf ..."
cp /etc/nginx/nginx.conf "$BACKUP_DIR/nginx-config/nginx.conf" 2>/dev/null && \
    echo "   ✅ nginx.conf" || echo "   ❌ nginx.conf"

# 4. Caddyfile
echo ""
echo "4. Copiando /etc/caddy/ ..."
for f in /etc/caddy/*.conf /etc/caddy/Caddyfile; do
    [ -f "$f" ] || continue
    name=$(basename "$f")
    cp "$f" "$BACKUP_DIR/caddy/$name" && \
        echo "   ✅ $name ($(wc -c < "$f") bytes)" || \
        echo "   ❌ $name"
done

# 5. DNS / Cloudflare info
echo ""
echo "5. Guardando estado DNS ..."
{
    echo "# Respaldo DNS — $TIMESTAMP"
    echo ""
    for domain in blog.enmexico.casa nexus.christmas enmexico.casa padim.enmexico.casa nexus.visionnorth.mx; do
        echo "### $domain"
        dig +short "$domain" A 2>/dev/null
        echo ""
    done
} > "$BACKUP_DIR/dns-status.txt"
echo "   ✅ DNS status guardado"

# 6. Manifest
echo ""
echo "6. Creando manifest ..."
cat > "$BACKUP_DIR/MANIFEST.md" <<EOF
# Respaldo Nginx — $TIMESTAMP

## Propósito
Respaldo completo de configuraciones de nginx antes de corregir
el catch-all en puerto 443 causado por admin-nexus.

## Archivos
- \`sites-available/\` — Configs originales de cada site
- \`sites-enabled/\` — Symlinks activos
- \`nginx-config/\` — nginx.conf principal
- \`caddy/\` — Configs de Caddy (incluye blog-padim.conf)
- \`dns-status.txt\` — Resolución DNS de dominios clave

## Estado actual (pre-fix)
- admin-nexus es el default implícito en puerto 443
- blog.enmexico.casa HTTPS → Approval Gate
- nexus.christmas HTTPS → Approval Gate
EOF
echo "   ✅ MANIFEST.md"

# 7. Resumen
echo ""
echo "═══════════════════════════════════════════"
echo "✅ Respaldo completado"
echo "📁 $BACKUP_DIR"
echo "📦 $(find "$BACKUP_DIR" -type f | wc -l) archivos"
echo "═══════════════════════════════════════════"
