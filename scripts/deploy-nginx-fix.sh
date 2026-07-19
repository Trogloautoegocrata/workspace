#!/bin/bash
# deploy-nginx-fix.sh — Corrige catch-all 443 y agrega SSL para blog.enmexico.casa y nexus.christmas
# Ejecutar: sudo bash /home/polaris/workspace/scripts/deploy-nginx-fix.sh

set -e

echo "═══════════════════════════════════════════"
echo "  🔧 DEPLOY: Fix nginx catch-all en 443"
echo "═══════════════════════════════════════════"
echo ""

BACKUP_DIR="/home/polaris/workspace/backup-nginx-20260719"
TMP_DIR="/home/polaris/workspace/tmp"
SITES_AVAILABLE="/etc/nginx/sites-available"
SITES_ENABLED="/etc/nginx/sites-enabled"

# 1. INSTALAR: catch-all default que rechaza conexiones
echo "1. Instalando catch-all default para 443..."
cp "$TMP_DIR/00-default-443-catch-all.nginx.conf" "$SITES_AVAILABLE/00-default-443-catch-all"
ln -sf "$SITES_AVAILABLE/00-default-443-catch-all" "$SITES_ENABLED/00-default-443-catch-all"
echo "   ✅ 00-default-443-catch-all"

# 2. INSTALAR: blog.enmexico.casa SSL
echo "2. Instalando SSL para blog.enmexico.casa..."
cp "$TMP_DIR/blog-enmexico-ssl.nginx.conf" "$SITES_AVAILABLE/blog-enmexico-ssl"
ln -sf "$SITES_AVAILABLE/blog-enmexico-ssl" "$SITES_ENABLED/blog-enmexico-ssl"
echo "   ✅ blog-enmexico-ssl"

# 3. INSTALAR: nexus.christmas SSL
echo "3. Instalando SSL para nexus.christmas..."
cp "$TMP_DIR/nexus-christmas-ssl.nginx.conf" "$SITES_AVAILABLE/nexus-christmas-ssl"
ln -sf "$SITES_AVAILABLE/nexus-christmas-ssl" "$SITES_ENABLED/nexus-christmas-ssl"
echo "   ✅ nexus-christmas-ssl"

# 4. DESHABILITAR: admin-nexus (remover su listen 443 default)
echo "4. Removiendo admin-nexus (ya no es necesario su SSL catch-all)..."
# No eliminamos el archivo, solo removemos del sites-enabled
rm -f "$SITES_ENABLED/admin-nexus"
echo "   ✅ admin-nexus deshabilitado de sites-enabled"
echo "   ⚠️  admin.nexus.christmas ya no será accesible via nginx"
echo "   ⚠️  Si se necesita: re-habilitar con ln -sf"

# 5. TEST: verificar config de nginx
echo ""
echo "5. Verificando configuración de nginx..."
nginx -t 2>&1 && echo "   ✅ Config OK" || {
    echo "   ❌ Config ERROR - revirtiendo..."
    # Rollback automático
    rm -f "$SITES_ENABLED/00-default-443-catch-all" "$SITES_ENABLED/blog-enmexico-ssl" "$SITES_ENABLED/nexus-christmas-ssl"
    rm -f "$SITES_AVAILABLE/00-default-443-catch-all" "$SITES_AVAILABLE/blog-enmexico-ssl" "$SITES_AVAILABLE/nexus-christmas-ssl"
    ln -sf "$SITES_AVAILABLE/admin-nexus" "$SITES_ENABLED/admin-nexus"
    echo "   ✅ Rollback completado"
    exit 1
}

# 6. RECARGAR: nginx
echo ""
echo "6. Recargando nginx..."
systemctl reload nginx 2>&1 && echo "   ✅ Nginx recargado" || {
    echo "   ❌ Error al recargar - revirtiendo..."
    rm -f "$SITES_ENABLED/00-default-443-catch-all" "$SITES_ENABLED/blog-enmexico-ssl" "$SITES_ENABLED/nexus-christmas-ssl"
    rm -f "$SITES_AVAILABLE/00-default-443-catch-all" "$SITES_AVAILABLE/blog-enmexico-ssl" "$SITES_AVAILABLE/nexus-christmas-ssl"
    ln -sf "$SITES_AVAILABLE/admin-nexus" "$SITES_ENABLED/admin-nexus"
    systemctl reload nginx 2>&1
    echo "   ✅ Rollback completado"
    exit 1
}

# 7. RESUMEN
echo ""
echo "═══════════════════════════════════════════"
echo "  ✅ DEPLOY COMPLETADO"
echo "═══════════════════════════════════════════"
echo ""
echo "Cambios realizados:"
echo "  + 00-default-443-catch-all → Rechaza conexiones 443 no coincidentes"
echo "  + blog-enmexico-ssl         → blog.enmexico.casa HTTPS → Caddy"
echo "  + nexus-christmas-ssl       → nexus.christmas HTTPS + HTTP"
echo "  - admin-nexus deshabilitado  → Ya no es el default de 443"
echo ""
echo "Prueba los endpoints:"
echo "  curl -sI https://blog.enmexico.casa/"
echo "  curl -skI https://nexus.christmas/"
echo "  curl -sk -H 'Host: random.xyz' https://127.0.0.1/  (debe dar error 444)"
echo ""
echo "═══════════════════════════════════════════"
