#!/usr/bin/env python3
"""
Pipeline Automatizado: SISTEMA 7 — LEAD SCORING
================================================
Configura el sistema de calificación automática de leads basado en
comportamiento, perfil, y engagement.
Cuando se ejecuta:
  1. Define factores de scoring por nicho
  2. Crea reglas de puntuación automática
  3. Configura routing por score (lead caliente → notificación)
  4. Crea pipeline de calificación
  5. Conecta con workflows de GHL
"""

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

BASE_DIR = Path("/home/polaris/workspace")

SCORING_MODELS = {
    "agente": {
        "name": "Lead Scoring — Broker",
        "factors": {
            "perfil": {
                "tiene_presupuesto": 30,
                "compro_en_ultimos_6m": 20,
                "tipo_comprador": {"primera_vivienda": 20, "inversionista": 25, "renta": 10},
                "zona_interes_especifica": 15
            },
            "comportamiento": {
                "abrio_email": 5,
                "hizo_click": 10,
                "solicito_brochure": 15,
                "agendo_cita": 25,
                "asistio_a_cita": 30,
                "visito_pagina_3_veces": 10,
                "descargo_lead_magnet": 15
            },
            "engagement": {
                "respondio_whatsapp": 10,
                "llamada_entrante": 20,
                "tiempo_en_sitio_mas_2min": 5,
                "compartio_propiedad": 15
            }
        },
        "thresholds": {
            "caliente": 80,
            "tibio": 50,
            "frio": 0
        },
        "actions": {
            "caliente": "notificar_inmediato + asignar_agente_top",
            "tibio": "nutricion_automatica + seguimiento_48h",
            "frio": "nutricion_larga + reactivacion_30d"
        }
    },
    "inmobiliaria": {
        "name": "Lead Scoring — Inmobiliaria",
        "factors": {
            "perfil": {
                "tiene_presupuesto": 25,
                "tipo_propiedad_definido": 15,
                "zona_especifica": 15,
                "plazo_compra_3_meses": 20
            },
            "comportamiento": {
                "abrio_email": 5,
                "hizo_click": 10,
                "solicito_brochure": 15,
                "agendo_cita": 25,
                "asistio_a_cita": 30,
                "visito_propiedad": 35,
                "descargo_lead_magnet": 10
            },
            "engagement": {
                "respondio_whatsapp": 10,
                "llamada_entrante": 20,
                "interactuo_con_ai_chat": 15,
                "compartio_propiedad": 15
            }
        },
        "thresholds": {"caliente": 80, "tibio": 50, "frio": 0},
        "actions": {
            "caliente": "notificar_agente_asignado + llamada_inmediata",
            "tibio": "nutricion_equipo + seguimiento_24h",
            "frio": "nutricion_masiva + reactivacion_45d"
        }
    },
    "desarrollador": {
        "name": "Lead Scoring — Desarrollador",
        "factors": {
            "perfil": {
                "tiene_enganche": 30,
                "buró_aprobado": 25,
                "tipo_unidad_definida": 15,
                "proyecto_conocido": 10
            },
            "comportamiento": {
                "solicito_brochure": 15,
                "agendo_visita_showroom": 25,
                "asistio_a_showroom": 35,
                "solicito_financiamiento": 30,
                "descargo_plan_de_pagos": 20
            },
            "engagement": {
                "respondio_whatsapp": 10,
                "llamada_entrante": 20,
                "visito_proyecto_3_veces_web": 10
            }
        },
        "thresholds": {"caliente": 80, "tibio": 50, "frio": 0},
        "actions": {
            "caliente": "notificar_asesor_preventa + apartado_inmediato",
            "tibio": "seguimiento_preventa + envio_brochure_comparativo",
            "frio": "campana_remarketing + nutricion_larga"
        }
    }
}

def run_pipeline(client_name, nicho, ghl_location_id, output_dir, mode):
    print(f"\n{'='*60}")
    print(f"  🎯 PIPELINE SISTEMA 7 — LEAD SCORING")
    print(f"  Cliente: {client_name}")
    print(f"  Nicho: {nicho.upper()}")
    print(f"  Modo: {mode.upper()}")
    print(f"{'='*60}\n")
    
    output_dir = Path(output_dir)
    model = SCORING_MODELS[nicho]
    
    model["for_client"] = client_name
    model["ghl_location_id"] = ghl_location_id
    model["created_at"] = datetime.now().isoformat()
    
    (output_dir / ".polaris" / "lead-scoring-model.json").write_text(json.dumps(model, indent=2))
    
    total_factors = sum(len(v) for v in model["factors"].values())
    
    print(f"  📊 Modelo: {model['name']}")
    print(f"  📋 Factores totales: {total_factors}")
    print(f"  📈 Thresholds: Caliente ≥80 | Tibio ≥50 | Frío <50")
    print(f"\n  Factores por categoría:")
    for category, factors in model["factors"].items():
        print(f"    • {category}: {len(factors)} factores ({sum(factors.values())} pts máx)")
    
    print(f"\n  Acciones por nivel de score:")
    for level, action in model["actions"].items():
        print(f"    🔥 {level.upper()} ({model['thresholds'][level]}+ pts) → {action}")
    
    print(f"\n{'='*60}")
    print(f"  ✅ PIPELINE COMPLETADO")
    print(f"  ⚠️  Activar desde GHL: Workflows → Lead Scoring Rules")
    print(f"{'='*60}\n")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline Sistema 7: Lead Scoring")
    parser.add_argument("--client-name", required=True)
    parser.add_argument("--nicho", required=True, choices=["agente", "inmobiliaria", "desarrollador"])
    parser.add_argument("--ghl-location-id", default="Y4aiZTaYX1nOxb6awqD7")
    parser.add_argument("--output-dir", default=str(BASE_DIR / "public"))
    parser.add_argument("--mode", default="standard", choices=["standard", "polaris"])
    args = parser.parse_args()
    run_pipeline(args.client_name, args.nicho, args.ghl_location_id, args.output_dir, args.mode)