#!/usr/bin/env python3
"""
Cron Automatizado: Pipeline Presencia Digital Polaris
Corre cada 6h para regenerar assets si cambió el logo.
Reporta solo si hubo cambios.
"""
import hashlib
import json
import os
import subprocess
import sys

LOGO_PATH = "/home/polaris/workspace/public/brand/LOGO-POLARIS.png"
STATE_FILE = "/home/polaris/workspace/scripts/.pipeline-presencia-state.json"
PIPELINE_SCRIPT = "/home/polaris/workspace/scripts/pipeline-presencia-digital.py"

def file_hash(path):
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"logo_hash": "", "last_run": None}

def save_state(hash_val):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump({"logo_hash": hash_val, "last_run": __import__("datetime").datetime.now().isoformat()}, f)

def main():
    if not os.path.exists(LOGO_PATH):
        print("❌ Logo no encontrado")
        sys.exit(1)
    
    current_hash = file_hash(LOGO_PATH)
    state = load_state()
    
    if state["logo_hash"] == current_hash and state["last_run"]:
        # Sin cambios, no hacer nada
        sys.exit(0)
    
    # El logo cambió o es primera ejecución → regenerar
    result = subprocess.run(
        ["python3", PIPELINE_SCRIPT,
         "--client-name", "Polaris by VisionNorth",
         "--logo", LOGO_PATH,
         "--domain", "back-bone.dev",
         "--output-dir", "/home/polaris/workspace/public",
         "--mode", "polaris"],
        capture_output=True, text=True
    )
    
    if result.returncode == 0:
        save_state(current_hash)
        print(f"🔄 Pipeline ejecutado: logo actualizado")
        print(result.stdout)
    else:
        print(f"❌ Pipeline falló: {result.stderr}")

if __name__ == "__main__":
    main()