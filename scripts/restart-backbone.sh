#!/bin/bash
# Restart BACKBONE API after tenant middleware update
# Ejecutar: sudo bash restart-backbone.sh

set -e
echo "🔁 Restaurando BACKBONE API con tenant middleware..."
sudo systemctl restart backbone-api
sleep 4
echo "📡 Estado:"
systemctl status backbone-api --no-pager | head -5
echo ""
echo "🔍 Health check:"
curl -s --max-time 5 http://localhost:8005/health | python3 -m json.tool
echo ""
echo "🔍 Sin tenant header (debe usar tenant_default):"
curl -s --max-time 5 "http://localhost:8005/v1/properties?per_page=1" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Total: {d.get(\"meta\",{}).get(\"total\",\"?\")}')"
echo ""
echo "🔍 Con tenant header (polaris_visionnorth - vacío por ahora):"
curl -s -H "X-Tenant-Id: polaris_visionnorth" --max-time 5 "http://localhost:8005/v1/properties?per_page=1" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Total: {d.get(\"meta\",{}).get(\"total\",\"?\")}')"
echo ""
echo "✅ Verificación completa"