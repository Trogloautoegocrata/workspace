#!/usr/bin/env bash
# 🏭 deploy-full-stack.sh — Despliegue completo de Polaris en un cliente
# Uso: ./deploy-full-stack.sh --name "Inmobiliaria X" --nicho inmobiliaria --plan accelerator --domain inmobiliariax.mx
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE="$(cd "$SCRIPT_DIR/.." && pwd)"
PUBLIC="$WORKSPACE/public"
POLARIS="$PUBLIC/.polaris"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║     🏭  POLARIS — DESPLIEGUE COMPLETO                   ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ─── Parse arguments ──────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case $1 in
    --name) CLIENT_NAME="$2"; shift 2 ;;
    --nicho) NICHO="$2"; shift 2 ;;
    --plan) PLAN="$2"; shift 2 ;;
    --domain) DOMAIN="$2"; shift 2 ;;
    --ghl-location) GHL_LOCATION="$2"; shift 2 ;;
    --ghl-key) GHL_KEY="$2"; shift 2 ;;
    --logo) LOGO="$2"; shift 2 ;;
    --budget-meta) BUDGET_META="$2"; shift 2 ;;
    *) echo -e "${RED}❌ Argumento desconocido: $1${NC}"; exit 1 ;;
  esac
done

# ─── Validate ────────────────────────────────────────────────────
: "${CLIENT_NAME:?❌ --name es obligatorio}"
: "${NICHO:?❌ --nicho es obligatorio (agente|inmobiliaria|desarrollador)}"
: "${PLAN:?❌ --plan es obligatorio (foundation|accelerator|domination)}"
: "${DOMAIN:=${CLIENT_NAME,,}-polaris.pw}"
: "${GHL_LOCATION:=Y4aiZTaYX1nOxb6awqD7}"
: "${GHL_KEY:=pit-1b1950d4-0e55-4246-bbbc-2d2d640e906c}"
: "${LOGO:=$PUBLIC/brand/LOGO-POLARIS.png}"
: "${BUDGET_META:=300}"

SLUG="${CLIENT_NAME,,}"
SLUG="${SLUG// /-}"

echo -e "${YELLOW}📋 Resumen de despliegue:${NC}"
echo "   Cliente:  $CLIENT_NAME"
echo "   Nicho:    $NICHO"
echo "   Plan:     $PLAN"
echo "   Dominio:  $DOMAIN"
echo ""

# ─── Step function ───────────────────────────────────────────────
run_pipeline() {
    local num=$1
    local name=$2
    local script=$3
    shift 3
    
    echo -e "${BLUE}[$num] $name${NC}"
    echo -e "      ${YELLOW}Ejecutando: $script${NC}"
    
    if python3 "$WORKSPACE/scripts/$script" "$@" 2>&1; then
        echo -e "      ${GREEN}✅ $name completado${NC}\n"
    else
        echo -e "      ${RED}❌ $name falló${NC}\n"
        return 1
    fi
}

# ─── Ejecutar pipelines según plan ───────────────────────────────

# Sistemas base (Foundation): siempre se ejecutan
echo -e "${GREEN}══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  📦 SISTEMAS BASE (Foundation)${NC}"
echo -e "${GREEN}══════════════════════════════════════════════════════════${NC}"

run_pipeline 1 "Presencia Digital" "pipeline-presencia-digital.py" \
    --client-name "$CLIENT_NAME" \
    --logo "$LOGO" \
    --domain "$DOMAIN" \
    --output-dir "$PUBLIC/$SLUG" \
    --mode standard

run_pipeline 2 "Captación Orgánica" "pipeline-captacion-organica.py" \
    --client-name "$CLIENT_NAME" \
    --domain "$DOMAIN" \
    --ghl-location-id "$GHL_LOCATION" \
    --topics "inmobiliario,automatizacion,crecimiento" \
    --output-dir "$PUBLIC/$SLUG" \
    --mode standard

run_pipeline 3 "Conversión" "pipeline-conversion.py" \
    --client-name "$CLIENT_NAME" \
    --domain "$DOMAIN" \
    --ghl-location-id "$GHL_LOCATION" \
    --ghl-api-key "$GHL_KEY" \
    --nicho "$NICHO" \
    --output-dir "$PUBLIC/$SLUG" \
    --mode standard

run_pipeline 4 "Agendamiento" "pipeline-agendamiento.py" \
    --client-name "$CLIENT_NAME" \
    --domain "$DOMAIN" \
    --ghl-location-id "$GHL_LOCATION" \
    --ghl-api-key "$GHL_KEY" \
    --nicho "$NICHO" \
    --output-dir "$PUBLIC/$SLUG" \
    --mode standard

# Sistemas avanzados (Accelerator / Domination)
if [[ "$PLAN" == "accelerator" || "$PLAN" == "domination" ]]; then
    echo -e "${GREEN}══════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  🚀 SISTEMAS AVANZADOS (Accelerator)${NC}"
    echo -e "${GREEN}══════════════════════════════════════════════════════════${NC}"

    run_pipeline 5 "Tráfico Pago Meta" "pipeline-trafico-pago.py" \
        --client-name "$CLIENT_NAME" \
        --domain "$DOMAIN" \
        --nicho "$NICHO" \
        --presupuesto-meta "$BUDGET_META" \
        --output-dir "$PUBLIC/$SLUG" \
        --mode standard

    run_pipeline 6 "Nutrición Avanzada" "pipeline-nutricion.py" \
        --client-name "$CLIENT_NAME" \
        --ghl-location-id "$GHL_LOCATION" \
        --output-dir "$PUBLIC/$SLUG" \
        --mode standard

    run_pipeline 7 "Lead Scoring" "pipeline-lead-scoring.py" \
        --client-name "$CLIENT_NAME" \
        --nicho "$NICHO" \
        --ghl-location-id "$GHL_LOCATION" \
        --output-dir "$PUBLIC/$SLUG" \
        --mode standard
fi

# ─── Reporte final ────────────────────────────────────────────────
echo -e "${GREEN}══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ DESPLIEGUE COMPLETO — $CLIENT_NAME${NC}"
echo -e "${GREEN}══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${YELLOW}📂 Assets generados en:${NC} $PUBLIC/$SLUG/"
echo -e "  ${YELLOW}⚙️  Config GHL en:${NC}       $PUBLIC/$SLUG/.polaris/"
echo ""
echo -e "  ${BLUE}📋 PRÓXIMOS PASOS (desde UI de GHL):${NC}"
echo "  1. Ir a Workflows → Publicar: Confirmación, Recordatorios, No-Show"
echo "  2. Ir a Calendarios → Verificar disponibilidad horaria"
echo "  3. Personalizar landing pages con contenido del cliente"
echo "  4. Verificar que el lead flow funciona (formulario → GHL → pipeline)"
echo ""
echo -e "  ${GREEN}💰 Resumen financiero:${NC}"
echo "  Plan: ${PLAN^^} | Retainer: \$[VER TABLA] | Setup: \$[VER TABLA]"
echo ""

# Guardar registro de despliegue
REGISTRO="$PUBLIC/$SLUG/.polaris/deploy-registry.json"
cat > "$REGISTRO" << EOF
{
  "cliente": "$CLIENT_NAME",
  "nicho": "$NICHO",
  "plan": "$PLAN",
  "dominio": "$DOMAIN",
  "fecha": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "sistemas_desplegados": [1,2,3,4$( [[ "$PLAN" != "foundation" ]] && echo ",5,6,7")]
}
EOF
echo -e "  📝 Registro guardado en: $REGISTRO"