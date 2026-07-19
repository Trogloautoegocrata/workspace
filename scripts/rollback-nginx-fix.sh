#!/bin/bash
# rollback-nginx-fix.sh — Revierte los cambios si algo sale mal
# Ejecutar: sudo bash /home/polaris/workspace/scripts/rollback-nginx-fix.sh

SITES_ENABLED="/etc/nginx/sites-enabled"
SITES_AVAILABLE="/etc/nginx/sites-available"

echo "═══════════════════════════════════════════"
echo "  ⚠️  ROLLBACK: Revirtiendo fix de nginx"
echo "═══════════════════════════════════════════"

# 1. Remover archivos nuevos
echo "1. Removiendo archivos nuevos..."
rm -f "$SITES_ENABLED/00-default-443-catch-all" 2>/dev/null && echo "   ✅ Removido 00-default-443-catch-all"
rm -f "$SITES_AVAILABLE/00-default-443-catch-all" 2>/dev/null && echo "   ✅ Removido 00-default-443-catch-all"
rm -f "$SITES_ENABLED/blog-enmexico-ssl" 2>/dev/null && echo "   ✅ Removido blog-enmexico-ssl"
rm -f "$SITES_AVAILABLE/blog-enmexico-ssl" 2>/dev/null && echo "   ✅ Removido blog-enmexico-ssl"
rm -f "$SITES_ENABLED/nexus-christmas-ssl" 2>/dev/null && echo "   ✅ Removido nexus-christmas-ssl"
rm -f "$SITES_AVAILABLE/nexus-christmas-ssl" 2>/dev/null && echo "   ✅ Removido nexus-christmas-ssl"

# 2. Restaurar admin-nexus (si fue deshabilitado)
echo "2. Restaurando admin-nexus..."
if [ -f "$SITES_AVAILABLE/admin-nexus" ]; then
    ln -sf "$SITES_AVAILABLE/admin-nexus" "$SITES_ENABLED/admin-nexus" 2>/dev/null
    echo "   ✅ admin-nexus re-habilitado"
fi

# 3. Verificar config
echo "3. Verificando config..."
nginx -t 2>&1 && echo "   ✅ Config OK" || echo "   ❌ Config sigue rota - revisar manualmente"

# 4. Recargar
echo "4. Recargando nginx..."
systemctl reload nginx 2>&1 && echo "   ✅ Nginx recargado" || echo "   ❌ Error recargando"

echo ""
echo "═══════════════════════════════════════════"
echo "  🔄 ROLLBACK COMPLETADO"
echo "  Estado original restaurado"
echo "═══════════════════════════════════════════"
