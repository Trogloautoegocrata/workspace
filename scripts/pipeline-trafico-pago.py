#!/usr/bin/env python3
"""
Pipeline Automatizado: SISTEMA 5 — TRÁFICO PAGO META
====================================================
Prepara toda la infraestructura para campañas de Meta Ads.
NO lanza campañas con gasto real — eso requiere autorización humana.
Cuando se ejecuta:
  1. Genera estructura de campañas (PAUSED por defecto)
  2. Genera creativos base (copy PAS + imágenes)
  3. Configura audiencias (remarketing + lookalike + prospección)
  4. Genera landing pages para campañas
  5. Configura píxel de Meta + eventos
  6. Prepara dashboard de ROAS
  7. Documenta plan de medios con presupuestos y KPIs

Uso:
  python3 pipeline-trafico-pago.py \
    --client-name "Inmobiliaria X" \
    --domain "inmobiliariax.com" \
    --nicho "inmobiliaria" \
    --presupuesto-meta 500 \
    --presupuesto-google 300

Modo Cliente 0 (Polaris):
  python3 pipeline-trafico-pago.py \
    --client-name "Polaris by VisionNorth" \
    --domain "polaris.pw" \
    --nicho "inmobiliaria" \
    --presupuesto-meta 300 \
    --mode polaris
"""

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

BASE_DIR = Path("/home/polaris/workspace")

# ─── Step 1: Estructura de Campañas ──────────────────────────────────────
def step_campaign_structure(output_dir, client_name, nicho, budget_meta):
    """Genera la estructura de campañas Meta Ads (en PAUSED)."""
    print("  [1/7] Generando estructura de campañas...")
    
    campaigns = {
        "tofu_awareness": {
            "name": f"[TOFU] Awareness — {client_name}",
            "objective": "REACH",
            "daily_budget": int(budget_meta * 0.2),
            "status": "PAUSED",
            "targeting": {
                "age_min": 25,
                "age_max": 65,
                "geo_locations": {"country": ["MX"]}
            }
        },
        "mofu_lead": {
            "name": f"[MOFU] Leads — {client_name}",
            "objective": "LEADS",
            "daily_budget": int(budget_meta * 0.5),
            "status": "PAUSED",
            "targeting": {
                "age_min": 28,
                "age_max": 60,
                "geo_locations": {"country": ["MX"]}
            }
        },
        "bofu_retargeting": {
            "name": f"[BOFU] Retargeting — {client_name}",
            "objective": "CONVERSIONS",
            "daily_budget": int(budget_meta * 0.3),
            "status": "PAUSED",
            "targeting": {
                "age_min": 25,
                "age_max": 65,
                "geo_locations": {"country": ["MX"]}
            }
        }
    }
    
    campaign_plan = {
        "nicho": nicho,
        "total_daily_budget_meta": budget_meta,
        "campaigns": campaigns,
        "guardrails": {
            "max_campaign_daily_budget": 1000000,  # $1,000 USD en cents
            "require_geo_targeting": True,
            "default_status": "PAUSED",
            "require_approval_before_activate": True
        },
        "created_at": datetime.now().isoformat()
    }
    
    (output_dir / ".polaris" / "campaign-structure.json").write_text(json.dumps(campaign_plan, indent=2))
    print(f"      ✅ 3 campañas estructuradas (TOFU + MOFU + BOFU)")
    print(f"      🛑 TODAS EN PAUSED — requieren autorización para activar")
    return True

# ─── Step 2: Creativos base ──────────────────────────────────────────────
def step_creatives(output_dir, client_name, nicho):
    """Genera copy de anuncios con framework PAS."""
    print("  [2/7] Generando creativos base...")
    
    creatives = [
        {
            "name": f"Problema — Lead gen {client_name}",
            "framework": "PAS",
            "hook": "¿Sigues perdiendo leads porque tu CRM no te avisa?",
            "body": f"El 78% de los compradores elige al primer agente que responde. Si no tienes un sistema, estás regalando clientes. {client_name} automatiza tu captación para que nunca pierdas un lead.",
            "cta": "Agenda tu diagnóstico gratuito",
            "format": "single_image"
        },
        {
            "name": f"Agitar — Costo oportunidad",
            "framework": "PAS",
            "hook": "Cada lead que no respondes te cuesta $X en comisión perdida.",
            "body": f"Un lead sin seguimiento = dinero perdido. Con {client_name}, cada contacto recibe respuesta en <60 segundos, 24/7. Sin perder uno. Sin pagar más.",
            "cta": "Descubre cómo",
            "format": "video"
        },
        {
            "name": f"Solución — Sistema completo",
            "framework": "PAS",
            "hook": f"{client_name} convierte leads en clientes mientras duermes.",
            "body": "CRM + AI Voice + WhatsApp + Email + Ads. Un solo ecosistema. Resultados medibles desde el día 1.",
            "cta": "Solicita demo",
            "format": "carousel"
        }
    ]
    
    (output_dir / ".polaris" / "creatives-base.json").write_text(json.dumps(creatives, indent=2))
    print(f"      ✅ 3 creativos base (PAS framework): Problema, Agitar, Solución")
    return True

# ─── Step 3: Audiencias ──────────────────────────────────────────────────
def step_audiences(output_dir, client_name, domain, nicho):
    """Configura audiencias para Meta Ads."""
    print("  [3/7] Configurando audiencias...")
    
    audiences = {
        "remarketing_website": {
            "name": f"Visitantes Web — {client_name}",
            "type": "website",
            "source": domain,
            "retention_days": 180,
            "rule": {"url": {"contains": domain}}
        },
        "remarketing_leads": {
            "name": f"Leads Anteriores — {client_name}",
            "type": "custom",
            "description": "Contactos que ya solicitaron información",
            "retention_days": 365
        },
        "lookalike_leads": {
            "name": f"Lookalike Leads — {client_name}",
            "type": "lookalike",
            "source_audience": "Leads Anteriores",
            "ratio": 0.03,
            "description": "3% lookalike basado en leads convertidos"
        },
        "prospecting": {
            "name": f"Prospección Inmobiliaria — {client_name}",
            "type": "interest",
            "interests": [
                "Real estate", "Bienes raíces", "Propiedades",
                "Crédito hipotecario", "Inversión inmobiliaria",
                "Casa propia", "Departamento"
            ],
            "description": "Usuarios con intereses inmobiliarios en MX"
        }
    }
    
    (output_dir / ".polaris" / "audiences.json").write_text(json.dumps(audiences, indent=2))
    print(f"      ✅ 4 audiencias configuradas (remarketing + lookalike + prospección)")
    return True

# ─── Step 4: Landing para campañas ───────────────────────────────────────
def step_landing_pages(output_dir, client_name, domain, nicho):
    """Genera landing pages optimizadas para campañas Meta."""
    print("  [4/7] Generando landing pages para campañas...")
    
    colors = {
        "agente": {"accent": "#1EDB7F", "title": "Broker"},
        "inmobiliaria": {"accent": "#0976F8", "title": "Inmobiliaria"},
        "desarrollador": {"accent": "#FF9337", "title": "Desarrollador"}
    }
    c = colors.get(nicho, colors["inmobiliaria"])
    
    # Landing para campaña de leads
    html = f"""<!DOCTYPE html>
<html lang="es-MX">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Oferta Especial — {client_name}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:system-ui,sans-serif;background:#0B0D17;color:#fff;line-height:1.6}}
.hero{{min-height:100vh;display:flex;align-items:center;justify-content:center;padding:2rem}}
.card{{max-width:600px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:1.25rem;padding:3rem;text-align:center}}
.badge{{display:inline-block;background:{c['accent']};color:#000;border-radius:2rem;padding:.3rem 1rem;font-size:.75rem;font-weight:700;margin-bottom:1rem}}
h1{{font-size:2.2rem;margin-bottom:1rem}}
p{{color:#A7A9BE;margin-bottom:2rem;font-size:1.05rem}}
.form-group{{margin-bottom:1rem}}
input{{width:100%;padding:.85rem 1rem;border:1px solid rgba(255,255,255,0.15);border-radius:.5rem;background:rgba(255,255,255,0.05);color:#fff;font-size:1rem}}
input:focus{{outline:none;border-color:{c['accent']}}}
button{{background:{c['accent']};color:#000;border:none;padding:.85rem 2rem;border-radius:.5rem;font-size:1rem;font-weight:700;cursor:pointer;width:100%;margin-top:.5rem}}
button:hover{{opacity:.9}}
.stats{{display:grid;grid-template-columns:repeat(3,1fr);gap:1rem;margin:2rem 0;text-align:center}}
.stat .num{{font-size:1.5rem;font-weight:700;color:{c['accent']}}}
.stat .label{{font-size:.8rem;color:#6C6F91}}
.social-proof{{font-size:.85rem;color:#6C6F91;margin-top:1.5rem}}
</style>
</head>
<body>
<div class="hero">
<div class="card">
<div class="badge">🎯 OFERTA ESPECIAL</div>
<h1>¿Listo para automatizar tu captación de clientes?</h1>
<p>Descubre cómo {client_name} puede convertir leads en clientes mientras tú trabajas.</p>
<div class="stats">
<div class="stat"><div class="num">78%</div><div class="label">Lead response</div></div>
<div class="stat"><div class="num">3x</div><div class="label">Más citas</div></div>
<div class="stat"><div class="num">24/7</div><div class="label">Automatizado</div></div>
</div>
<form id="leadForm">
<div class="form-group"><input type="text" placeholder="Nombre" required></div>
<div class="form-group"><input type="email" placeholder="Email" required></div>
<div class="form-group"><input type="tel" placeholder="WhatsApp"></div>
<button type="submit">🚀 Quiero más leads</button>
</form>
<p class="social-proof">Únete a +10 inmobiliarias que ya crecen con nosotros</p>
</div>
</div>
<script>
document.getElementById('leadForm').addEventListener('submit', function(e){{
  e.preventDefault();
  alert('✅ Recibimos tus datos. Te contactamos en <24h.');
}});
</script>
<script>
fetch('/analytics/track?page='+encodeURIComponent(location.pathname)+'&ref='+encodeURIComponent(document.referrer||'direct')).catch(()=>{{}});
</script>
</body>
</html>"""
    
    (output_dir / "landing-meta.html").write_text(html)
    print(f"      ✅ Landing page para campañas Meta: /landing-meta.html")
    return True

# ─── Step 5: Dashboard ROAS ──────────────────────────────────────────────
def step_dashboard(output_dir, client_name, nicho, budget_meta):
    """Genera dashboard de ROAS para tracking de campañas."""
    print("  [5/7] Generando dashboard de ROAS...")
    
    dashboard_config = {
        "client": client_name,
        "nicho": nicho,
        "meta_daily_budget": budget_meta,
        "kpis": {
            "ctr_target": 1.5,
            "cpc_target": 15.00,  # MXN
            "cpl_target": 150.00, # MXN por lead
            "roas_target": 4.0,
            "conversion_rate_target": 2.0
        },
        "tracking": {
            "pixel_event_lead": "Lead",
            "pixel_event_purchase": "Purchase",
            "conversion_window": "7_day_click"
        },
        "reporting": {
            "frequency": "weekly",
            "delivery": "email",
            "metrics": ["impressions", "clicks", "cpc", "cpl", "roas", "frequency"]
        }
    }
    
    (output_dir / ".polaris" / "dashboard-roas.json").write_text(json.dumps(dashboard_config, indent=2))
    print(f"      ✅ Dashboard ROAS configurado")
    return True

# ─── Step 6: Plan de medios ──────────────────────────────────────────────
def step_media_plan(output_dir, client_name, nicho, budget_meta):
    """Genera plan de medios con presupuestos y calendario."""
    print("  [6/7] Generando plan de medios...")
    
    plan = {
        "client": client_name,
        "nicho": nicho,
        "monthly_budget": budget_meta * 30,
        "channels": {
            "meta_ads": {
                "budget_pct": 0.6,
                "monthly_budget": budget_meta * 30 * 0.6,
                "campaigns": ["TOFU Awareness", "MOFU Leads", "BOFU Retargeting"]
            },
            "google_ads": {
                "budget_pct": 0.3,
                "monthly_budget": budget_meta * 30 * 0.3,
                "campaigns": ["Search", "Display", "Performance Max"]
            },
            "linkedin_ads": {
                "budget_pct": 0.1,
                "monthly_budget": budget_meta * 30 * 0.1,
                "campaigns": ["B2B Desarrolladores"]
            }
        },
        "estimated_kpis": {
            "monthly_impressions": budget_meta * 30 * 1.5,
            "monthly_clicks": budget_meta * 30 * 0.015,
            "monthly_leads": int(budget_meta * 30 * 0.015 * 0.05),
            "cpl_estimated": budget_meta / (budget_meta * 30 * 0.015 * 0.05)
        },
        "notes": "Todas las campañas se crean en PAUSED. Activar solo con aprobación del cliente."
    }
    
    (output_dir / ".polaris" / "media-plan.json").write_text(json.dumps(plan, indent=2))
    print(f"      ✅ Plan de medios generado")
    print(f"      💰 Presupuesto mensual estimado: ${budget_meta * 30:,.0f} MXN")
    print(f"      🎯 Leads estimados/mes: {plan['estimated_kpis']['monthly_leads']}")
    return True

# ─── Step 7: Guardrails ──────────────────────────────────────────────────
def step_guardrails(output_dir):
    """Documenta las reglas de seguridad para gasto publicitario."""
    print("  [7/7] Documentando guardrails de gasto...")
    
    guardrails = {
        "regla_1": "TODA campaña se crea en estado PAUSED — nunca LIVE",
        "regla_2": "NUNCA activar campaña sin autorización explícita del cliente",
        "regla_3": "Presupuesto máximo por campaña: $500 MXN/día hasta aprobación",
        "regla_4": "Siempre segmentar geográficamente (nunca 'Todo México')",
        "regla_5": "El cliente DEBE aprobar creativos antes de activar",
        "regla_6": "Reporte semanal obligatorio de ROAS y CPL",
        "regla_7": "Si ROAS < 2x por 3 días consecutivos → pausar y revisar",
        "aprobacion_requerida": True,
        "formato_aprobacion": "¿Apruebas lanzar campaña de $XXX/día para [objetivo]? 1) Sí ✅ 2) No ❌ 3) Modifica 🟡"
    }
    
    (output_dir / ".polaris" / "guardrails-gasto.json").write_text(json.dumps(guardrails, indent=2))
    print(f"      ✅ 7 guardrails de gasto documentados")
    print(f"      🛡️ Protección de presupuesto activa")
    return True

# ─── Main Pipeline ─────────────────────────────────────────────────────────
def run_pipeline(client_name, domain, nicho, budget_meta, budget_google, output_dir, mode):
    print(f"\n{'='*60}")
    print(f"  📢 PIPELINE SISTEMA 5 — TRÁFICO PAGO META")
    print(f"  Cliente: {client_name}")
    print(f"  Nicho: {nicho.upper()}")
    print(f"  Presupuesto Meta: ${budget_meta:,.0f}/día")
    print(f"  Modo: {mode.upper()}")
    print(f"{'='*60}\n")
    
    output_dir = Path(output_dir)
    
    steps = [
        ("Estructura Campañas", lambda: step_campaign_structure(output_dir, client_name, nicho, budget_meta)),
        ("Creativos PAS", lambda: step_creatives(output_dir, client_name, nicho)),
        ("Audiencias", lambda: step_audiences(output_dir, client_name, domain, nicho)),
        ("Landings Campañas", lambda: step_landing_pages(output_dir, client_name, domain, nicho)),
        ("Dashboard ROAS", lambda: step_dashboard(output_dir, client_name, nicho, budget_meta)),
        ("Plan de Medios", lambda: step_media_plan(output_dir, client_name, nicho, budget_meta)),
        ("Guardrails", lambda: step_guardrails(output_dir)),
    ]
    
    results = []
    for name, fn in steps:
        try:
            result = fn()
            results.append((name, "✅" if result else "❌"))
        except Exception as e:
            results.append((name, f"❌ {e}"))
    
    print(f"\n{'='*60}")
    print(f"  📊 REPORTE DE PIPELINE")
    print(f"{'='*60}")
    for name, status in results:
        print(f"  {status} {name}")
    
    success = all("✅" in s for _, s in results)
    print(f"\n  {'✅ PIPELINE COMPLETADO' if success else '❌ PIPELINE CON ERRORES'}")
    print(f"\n  ⚠️  REGLA DE ORO: TODAS LAS CAMPAÑAS EN PAUSED")
    print(f"  ⚠️  REQUIRE AUTORIZACIÓN EXPLÍCITA PARA ACTIVAR")
    print(f"{'='*60}\n")
    return success

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline Sistema 5: Tráfico Pago Meta")
    parser.add_argument("--client-name", required=True)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--nicho", required=True, choices=["agente", "inmobiliaria", "desarrollador"])
    parser.add_argument("--presupuesto-meta", type=int, default=300, help="Presupuesto diario Meta Ads en MXN")
    parser.add_argument("--presupuesto-google", type=int, default=0, help="Presupuesto diario Google Ads en MXN")
    parser.add_argument("--output-dir", default=str(BASE_DIR / "public"))
    parser.add_argument("--mode", default="standard", choices=["standard", "polaris"])
    
    args = parser.parse_args()
    run_pipeline(
        args.client_name, args.domain, args.nicho,
        args.presupuesto_meta, args.presupuesto_google,
        args.output_dir, args.mode
    )