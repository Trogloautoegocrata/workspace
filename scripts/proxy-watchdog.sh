#!/bin/bash
# Watchdog para proxy 8004 -> 8005
# Se ejecuta como cron cada 5 min, verifica y reinicia si es necesario

PID_FILE="/tmp/proxy_8004.pid"
LOG="/tmp/proxy_watchdog.log"

# Verificar si el proxy respondé
if curl -s -o /dev/null -m 3 http://localhost:8004/health 2>/dev/null; then
    exit 0
fi

# No responde — matar zombie si existe
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    kill "$OLD_PID" 2>/dev/null
    fuser -k 8004/tcp 2>/dev/null
fi

# Esperar a que el puerto se libere
sleep 1

# Levantar proxy
cd /home/polaris/workspace
source /home/polaris/workspace/projects/BACKBONE/.venv/bin/activate
nohup python3 proxy_8004_to_8005.py > /tmp/proxy_8004.log 2>&1 &
echo $! > "$PID_FILE"

echo "[$(date)] Proxy reiniciado PID $!" >> "$LOG"
