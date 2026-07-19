#!/usr/bin/env python3
"""
WEBHOOK RECEIVER — Puente entre GHL y los Pipelines de Automatización
=====================================================================
Recibe webhooks de GHL cuando un contacto cambia de etapa en un pipeline
y ejecuta el pipeline de automatización correspondiente.

Endpoints:
  POST /webhook/pipeline/s01-presencia-digital
    Body: {
      "contact_id": "xxx",
      "location_id": "xxx",
      "cliente": "Inmobiliaria XYZ",
      "logo_url": "https://...",
      "dominio": "inmobiliariaxyz.com",
      "color_primario": "#0B0D17",
      "color_accento": "#f59e0b",
      "nicho": "inmobiliaria"
    }

Trigger en GHL:
  Workflow: "Onboarding → Presencia Digital"
  Trigger: Contacto entra a etapa "Implementación" en Pipeline de Implementación
  Action: Webhook POST a este endpoint
"""

import json
import os
import subprocess
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

PIPELINES_DIR = os.path.expanduser("~/workspace/scripts")
LOG_FILE = os.path.expanduser("~/workspace/webhook-logs.json")

class WebhookHandler(BaseHTTPRequestHandler):
    
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        
        try:
            data = json.loads(body)
        except:
            self._respond(400, {"error": "Invalid JSON"})
            return
        
        path = urlparse(self.path).path
        result = self._route(path, data)
        
        if result["success"]:
            self._respond(200, result)
        else:
            self._respond(500, result)
    
    def _route(self, path, data):
        routes = {
            "/webhook/pipeline/s01-presencia-digital": self._run_s01_presencia_digital,
        }
        
        handler = routes.get(path)
        if not handler:
            return {"success": False, "error": f"Unknown route: {path}"}
        
        try:
            return handler(data)
        except Exception as e:
            self._log_error(path, data, str(e))
            return {"success": False, "error": str(e)}
    
    def _run_s01_presencia_digital(self, data):
        """Ejecuta pipeline de Presencia Digital Completa"""
        cliente = data.get("cliente")
        logo = data.get("logo_url")
        dominio = data.get("dominio")
        color_p = data.get("color_primario", "#0B0D17")
        color_a = data.get("color_accento", "#f59e0b")
        nicho = data.get("nicho", "agente")
        
        # Construir comando
        cmd = [
            "python3",
            f"{PIPELINES_DIR}/pipeline-presencia-digital.py",
            f"--cliente={cliente}",
            f"--logo={logo}",
            f"--dominio={dominio}",
            f"--color-primario={color_p}",
            f"--color-accento={color_a}",
            f"--nicho={nicho}",
        ]
        
        result = subprocess.run(" ".join(cmd), shell=True, capture_output=True, text=True, timeout=120)
        
        success = result.returncode == 0
        
        self._log_execution("S01", cliente, dominio, success, 
                           stdout=result.stdout[:500], 
                           stderr=result.stderr[:500])
        
        return {
            "success": success,
            "sistema": "S01-Presencia-Digital-Completa",
            "cliente": cliente,
            "dominio": dominio,
            "output": result.stdout[:200] if success else result.stderr[:200]
        }
    
    def _log_execution(self, sistema, cliente, dominio, success, **extra):
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        logs = []
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE) as f:
                try: logs = json.load(f)
                except: pass
        
        entry = {
            "timestamp": __import__("datetime").datetime.now().isoformat(),
            "sistema": sistema,
            "cliente": cliente,
            "dominio": dominio,
            "success": success,
            **extra
        }
        logs.append(entry)
        with open(LOG_FILE, "w") as f:
            json.dump(logs[-100:], f, indent=2)  # Keep last 100
    
    def _log_error(self, path, data, error):
        self._log_execution("ERROR", str(data.get("cliente", "?")), "", False,
                           error=error, path=path)
    
    def _respond(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def log_message(self, format, *args):
        pass  # Silent

if __name__ == "__main__":
    port = 8098
    server = HTTPServer(("0.0.0.0", port), WebhookHandler)
    print(f"🔌 Webhook Receiver corriendo en puerto {port}")
    print(f"   POST /webhook/pipeline/s01-presencia-digital")
    print(f"   Logs: webhook-logs.json")
    server.serve_forever()