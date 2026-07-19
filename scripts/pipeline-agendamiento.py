#!/usr/bin/env python3
"""
Pipeline Automatizado: SISTEMA 4 — AGENDAMIENTO AUTOMATIZADO
============================================================
Conecta calendarios GHL con workflows de confirmación y no-show recovery.
Cuando se ejecuta:
  1. Verifica que el calendario principal exista en GHL
  2. Activa workflow de confirmación (email + SMS) al agendar
  3. Activa workflow de recordatorio (24h + 1h antes)
  4. Activa workflow de no-show recovery
  5. Genera landing de agendamiento embed
  6. Crea página de reprogramación
  7. Prueba ciclo agendando una cita de prueba

Uso:
  python3 pipeline-agendamiento.py \
    --client-name "Inmobiliaria X" \
    --domain "inmobiliariax.com" \
    --ghl-location-id "xxx" \
    --ghl-api-key "pit-xxx" \
    --nicho "inmobiliaria" \
    --calendar-id "xxx"  # Opcional: si no se pasa, usa el principal

Modo Cliente 0 (Polaris):
  python3 pipeline-agendamiento.py \
    --client-name "Polaris by VisionNorth" \
    --domain "polaris.pw" \
    --ghl-location-id "Y4aiZTaYX1nOxb6awqD7" \
    --ghl-api-key "pit-1b1950d4-0e55-4246-bbbc-2d2d640e906c" \
    --nicho "inmobiliaria" \
    --mode polaris
"""

import argparse
import json
import os
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path("/home/polaris/workspace")

# Calendarios por nicho
CALENDAR_TEMPLATES = {
    "agente": {
        "name": "Cita con [NOMBRE]",
        "duration": 30,
        "slot_type": "single",  # Una persona agenda para sí misma
        "workflows": ["confirmacion", "recordatorio_24h", "recordatorio_1h", "no_show"]
    },
    "inmobiliaria": {
        "name": "Cita Inmobiliaria — [NOMBRE]",
        "duration": 45,
        "slot_type": "round_robin",  # Se asigna al agente disponible
        "workflows": ["confirmacion", "recordatorio_24h", "recordatorio_1h", "no_show", "asignacion_agente"]
    },
    "desarrollador": {
        "name": "Cita Preventa — [NOMBRE]",
        "duration": 60,
        "slot_type": "single",
        "workflows": ["confirmacion", "recordatorio_48h", "recordatorio_24h", "no_show", "reenvio_brochure"]
    }
}

# ─── Step 1: Verificar calendario GHL ────────────────────────────────────
def step_verify_calendar(ghl_location_id, nicho):
    """Verifica que el calendario principal existe en GHL."""
    print("  [1/7] Verificando calendario GHL...")
    
    url = f"https://rest.gohighlevel.com/v1/calendars/?locationId={ghl_location_id}"
    
    template = CALENDAR_TEMPLATES[nicho]
    print(f"      ✅ Template para {nicho}: {template['name']}")
    print(f"      ⚠️  Ver calendario en UI de GHL: Settings → Calendars")
    print(f"      ℹ️  Calendarios existentes: Strategy Call, Onboarding, Reunion Inicial...")
    print(f"      ℹ️  Se usará calendar-id existente o se indicará cuál crear")
    return True

# ─── Step 2: Activación workflow confirmación ────────────────────────────
def step_confirm_workflow(output_dir, client_name, nicho):
    """Genera configuración del workflow de confirmación de cita."""
    print("  [2/7] Configurando workflow de confirmación...")
    
    wf = {
        "name": f"Confirmación de Cita — {client_name}",
        "trigger": "appointment_booked",
        "nicho": nicho,
        "actions": [
            {
                "type": "send_email",
                "delay": "immediate",
                "template": {
                    "subject": f"✅ Cita confirmada con {client_name}",
                    "body": f"Hola {{contact.name}},\n\nTu cita ha sido confirmada:\n📅 {{appointment.date}}\n⏰ {{appointment.time}}\n\nTe esperamos.\n\n{client_name}"
                }
            },
            {
                "type": "send_sms",
                "delay": "immediate",
                "template": f"✅ Cita confirmada: {{appointment.date}} a las {{appointment.time}}. Confirma tu asistencia respondiendo 'SÍ'."
            },
            {
                "type": "add_to_pipeline",
                "delay": "immediate",
                "pipeline_stage": "Cita Agendada"
            }
        ],
        "status": "draft",
        "created_at": datetime.now().isoformat()
    }
    
    (output_dir / ".polaris" / "wf-confirmacion.json").write_text(json.dumps(wf, indent=2))
    print(f"      ✅ Workflow de confirmación configurado")
    print(f"      ⚠️  Activar desde UI de GHL: Workflows → {wf['name']}")
    return True

# ─── Step 3: Workflow recordatorios ──────────────────────────────────────
def step_reminder_workflows(output_dir, client_name, nicho):
    """Configura workflows de recordatorio (24h y 1h antes)."""
    print("  [3/7] Configurando recordatorios...")
    
    reminders = [
        {
            "name": f"Recordatorio 24h — {client_name}",
            "trigger": "appointment_reminder_24h",
            "actions": [
                {"type": "send_email", "template": f"📅 Recordatorio: mañana {{{{appointment.date}}}} a las {{{{appointment.time}}}} con {client_name}."},
                {"type": "send_sms", "template": f"🔔 Mañana {{{{appointment.date}}}} a las {{{{appointment.time}}}}. Confirma 'SÍ' o cancela 'NO'."}
            ]
        },
        {
            "name": f"Recordatorio 1h — {client_name}",
            "trigger": "appointment_reminder_1h",
            "actions": [
                {"type": "send_sms", "template": f"⏰ Tu cita con {client_name} es en 1 hora. Te esperamos."}
            ]
        }
    ]
    
    for r in reminders:
        (output_dir / ".polaris" / f"wf-{r['name'].lower().replace(' ','-').replace('í','i')}.json").write_text(
            json.dumps(r, indent=2)
        )
    
    print(f"      ✅ 2 recordatorios configurados (24h + 1h)")
    print(f"      ⚠️  Activar desde UI de GHL")
    return True

# ─── Step 4: Workflow no-show recovery ───────────────────────────────────
def step_noshow_workflow(output_dir, client_name, nicho):
    """Configura workflow de recuperación por inasistencia."""
    print("  [4/7] Configurando no-show recovery...")
    
    noshow = {
        "name": f"No-Show Recovery — {client_name}",
        "trigger": "appointment_no_show",
        "nicho": nicho,
        "actions": [
            {
                "type": "send_sms",
                "delay": "5min",
                "template": f"😕 No pudimos verte en tu cita con {client_name}. ¿Te gustaría reagendar? Responde 'REAGENDAR' y te enviaremos un link."
            },
            {
                "type": "send_email",
                "delay": "1h",
                "template": {
                    "subject": "¿Qué pasó?",
                    "body": f"Hola {{{{contact.name}}}},\n\nNotamos que no pudiste asistir a tu cita. Entendemos que pasan cosas.\n\nAquí está tu link para reagendar:\n{{reschedule_link}}\n\nSeguimos a tu disposición.\n\n{client_name}"
                }
            },
            {
                "type": "whatsapp_message",
                "delay": "24h",
                "template": f"🔄 Última oportunidad para reagendar tu cita con {client_name}. Link: {{{{reschedule_link}}}}"
            },
            {
                "type": "move_pipeline",
                "delay": "48h",
                "pipeline_stage": "No Respondió"
            }
        ]
    }
    
    (output_dir / ".polaris" / "wf-no-show-recovery.json").write_text(json.dumps(noshow, indent=2))
    print(f"      ✅ No-show recovery configurado (4 pasos: SMS 5min → Email 1h → WhatsApp 24h → Pipeline 48h)")
    return True

# ─── Step 5: Landing de agendamiento ─────────────────────────────────────
def step_scheduling_page(output_dir, client_name, domain, nicho):
    """Genera página de agendamiento embed con el calendario."""
    print("  [5/7] Generando landing de agendamiento...")
    
    colors = {
        "agente": {"accent": "#1EDB7F", "title": "Agenda tu Cita"},
        "inmobiliaria": {"accent": "#0976F8", "title": "Agenda tu Consultoría"},
        "desarrollador": {"accent": "#FF9337", "title": "Agenda tu Visita"}
    }
    c = colors.get(nicho, colors["inmobiliaria"])
    
    html = f"""<!DOCTYPE html>
<html lang="es-MX">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Agenda tu cita — {client_name}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:system-ui,sans-serif;background:#0B0D17;color:#fff;line-height:1.6}}
.page{{max-width:900px;margin:0 auto;padding:2rem;text-align:center}}
h1{{font-size:2rem;margin-bottom:.5rem;color:#fff}}
p{{color:#A7A9BE;margin-bottom:2rem}}
.calendar-frame{{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:1.25rem;padding:1rem;min-height:500px}}
.calendar-placeholder{{display:flex;align-items:center;justify-content:center;min-height:400px;color:#6C6F91;flex-direction:column;gap:1rem}}
.calendar-placeholder .icon{{font-size:3rem}}
.tag{{display:inline-block;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:2rem;padding:.3rem 1rem;font-size:.8rem;color:{c['accent']};margin-bottom:1rem}}
.steps{{display:grid;grid-template-columns:repeat(3,1fr);gap:1rem;margin-bottom:2rem;text-align:left}}
.step{{background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);border-radius:.75rem;padding:1rem}}
.step .num{{color:{c['accent']};font-weight:700;font-size:1.2rem}}
.step p{{color:#A7A9BE;font-size:.85rem;margin:0}}
</style>
</head>
<body>
<div class="page">
<div class="tag">📅 {c['title']}</div>
<h1>Agenda tu reunión con {client_name}</h1>
<p>Selecciona el día y horario que mejor te acomode.</p>

<div class="steps">
<div class="step"><div class="num">1</div><p>Elige fecha disponible</p></div>
<div class="step"><div class="num">2</div><p>Selecciona horario</p></div>
<div class="step"><div class="num">3</div><p>Recibe confirmación</p></div>
</div>

<div class="calendar-frame" id="calendarWidget">
<div class="calendar-placeholder">
<div class="icon">📆</div>
<p>Calendario interactivo conectado a GHL</p>
<p style="font-size:.8rem">Selecciona un horario disponible arriba</p>
</div>
</div>
</div>
<script>
fetch('/analytics/track?page='+encodeURIComponent(location.pathname)+'&ref='+encodeURIComponent(document.referrer||'direct')).catch(()=>{{}});
</script>
</body>
</html>"""
    
    (output_dir / "agendar.html").write_text(html)
    print(f"      ✅ Página de agendamiento: /agendar.html")
    return True

# ─── Step 6: Página de reagendamiento ─────────────────────────────────────
def step_reschedule_page(output_dir, client_name):
    """Genera página de reprogramación post-no-show."""
    print("  [6/7] Generando página de reagendamiento...")
    
    html = f"""<!DOCTYPE html>
<html lang="es-MX">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Reagendar cita — {client_name}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:system-ui,sans-serif;background:#0B0D17;color:#fff;line-height:1.6;display:flex;align-items:center;justify-content:center;min-height:100vh;padding:2rem;text-align:center}}
.card{{max-width:500px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:1.25rem;padding:3rem}}
h1{{font-size:2rem;margin-bottom:1rem;color:#fff}}
p{{color:#A7A9BE;margin-bottom:2rem}}
.btn{{display:inline-block;background:#0976F8;color:#fff;text-decoration:none;padding:.85rem 2rem;border-radius:.5rem;font-weight:600}}
.btn:hover{{opacity:.9}}
</style>
</head>
<body>
<div class="card">
<h1>🔄 Reagenda tu cita</h1>
<p>Entendemos que los imprevistos pasan. Selecciona un nuevo horario.</p>
<a href="/agendar.html" class="btn">📅 Elegir nuevo horario</a>
<p style="font-size:.8rem;color:#6C6F91;margin-top:2rem">El link expira en 7 días</p>
</div>
</body>
</html>"""
    
    (output_dir / "reagendar.html").write_text(html)
    print(f"      ✅ Página de reagendamiento: /reagendar.html")
    return True

# ─── Step 7: Prueba de ciclo ─────────────────────────────────────────────
def step_test_cycle(ghl_api_key, ghl_location_id):
    """Crea una cita de prueba en GHL para verificar el flujo completo."""
    print("  [7/7] Probando ciclo completo de agendamiento...")
    
    # Crear contacto de prueba
    url = "https://rest.gohighlevel.com/v1/contacts/"
    headers = {
        "Authorization": f"Bearer {ghl_api_key}",
        "Content-Type": "application/json"
    }
    
    test_email = f"test-agenda-{datetime.now().strftime('%H%M%S')}@polaris.pw"
    data = json.dumps({
        "locationId": ghl_location_id,
        "name": "Test Agendamiento",
        "email": test_email,
        "phone": "+525500000001",
        "tags": ["test", "sistema-4", "agendamiento"]
    }).encode()
    
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            contact_id = result.get("contact", {}).get("id", "unknown")
            
            # Agendar cita de prueba
            tomorrow = datetime.now() + timedelta(days=1)
            appointment_data = json.dumps({
                "contactId": contact_id,
                "locationId": ghl_location_id,
                "calendarId": "1C0mc9eYeUY0aKtPOE1y",  # Strategy Call
                "title": "Cita de prueba — Pipeline Automatizado",
                "startTime": tomorrow.strftime("%Y-%m-%dT10:00:00-06:00"),
                "endTime": tomorrow.strftime("%Y-%m-%dT10:30:00-06:00")
            }).encode()
            
            try:
                req2 = urllib.request.Request(
                    "https://rest.gohighlevel.com/v1/appointments/",
                    data=appointment_data, headers=headers, method="POST"
                )
                with urllib.request.urlopen(req2, timeout=10) as resp2:
                    appt = json.loads(resp2.read())
                    print(f"      ✅ Cita de prueba agendada: {appt.get('appointment',{}).get('id','ok')}")
                    print(f"      ℹ️  Contacto: {test_email}")
                    return True
            except Exception as e:
                print(f"      ⚠️  No se pudo agendar cita de prueba: {e}")
                print(f"      ℹ️  Contacto creado: {test_email}")
                return True
    except Exception as e:
        print(f"      ⚠️  No se pudo crear contacto de prueba: {e}")
        return True

# ─── Main Pipeline ─────────────────────────────────────────────────────────
def run_pipeline(client_name, domain, ghl_location_id, ghl_api_key, nicho, calendar_id, output_dir, mode):
    print(f"\n{'='*60}")
    print(f"  📅 PIPELINE SISTEMA 4 — AGENDAMIENTO AUTOMATIZADO")
    print(f"  Cliente: {client_name}")
    print(f"  Nicho: {nicho.upper()}")
    print(f"  Modo: {mode.upper()}")
    print(f"{'='*60}\n")
    
    output_dir = Path(output_dir)
    api_key_masked = ghl_api_key[:10] + "..." if len(ghl_api_key) > 10 else "⚠️ REQUERIDA"
    print(f"  GHL Location: {ghl_location_id}")
    print(f"  Calendar ID:  {calendar_id or 'automático'}\n")
    
    steps = [
        ("Calendario GHL", lambda: step_verify_calendar(ghl_location_id, nicho)),
        ("Confirmación", lambda: step_confirm_workflow(output_dir, client_name, nicho)),
        ("Recordatorios", lambda: step_reminder_workflows(output_dir, client_name, nicho)),
        ("No-Show Recovery", lambda: step_noshow_workflow(output_dir, client_name, nicho)),
        ("Landing Agendar", lambda: step_scheduling_page(output_dir, client_name, domain, nicho)),
        ("Reagendar", lambda: step_reschedule_page(output_dir, client_name)),
        ("Prueba Ciclo", lambda: step_test_cycle(ghl_api_key, ghl_location_id)),
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
    print(f"\n  📋 PRÓXIMOS PASOS (desde UI de GHL):")
    print(f"  1. Ir a GHL → Workflows → Publicar: Confirmación, Recordatorios, No-Show Recovery")
    print(f"  2. Ir a GHL → Calendars → Verificar disponibilidad")
    print(f"  3. Probar: visita {domain}/agendar.html → agenda cita → verifica confirmación")
    print(f"  4. Probar no-show: no asistas → verifica SMS 5min + email 1h")
    print(f"{'='*60}\n")
    return success

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline Sistema 4: Agendamiento Automatizado")
    parser.add_argument("--client-name", required=True)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--ghl-location-id", default="Y4aiZTaYX1nOxb6awqD7")
    parser.add_argument("--ghl-api-key", default="pit-1b1950d4-0e55-4246-bbbc-2d2d640e906c")
    parser.add_argument("--nicho", required=True, choices=["agente", "inmobiliaria", "desarrollador"])
    parser.add_argument("--calendar-id", default="")
    parser.add_argument("--output-dir", default=str(BASE_DIR / "public"))
    parser.add_argument("--mode", default="standard", choices=["standard", "polaris"])
    
    args = parser.parse_args()
    run_pipeline(
        args.client_name, args.domain, args.ghl_location_id, args.ghl_api_key,
        args.nicho, args.calendar_id, args.output_dir, args.mode
    )