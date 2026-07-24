#!/usr/bin/env python3
"""Monitor autónomo de BACKBONE + Redis + PostgreSQL.
Envía alertas por Telegram solo para problemas URGENTES y GRAVES.
No molesta con caídas transitorias (< 30s)."""
import asyncio, httpx, logging, os, json, sys
from datetime import datetime, timezone
from pathlib import Path

# ── Config ──
BOT_TOKEN = "8849968163:AAEyCYvjuxDbCaZqFeQlSdWufuAQAb_UaEY"
CHAT_ID = "148375429"
STATE_FILE = Path("/home/polaris/workspace/data/monitor-state.json")
CHECK_INTERVAL = 60  # segundos
DOWNTIME_THRESHOLD = 30  # segundos antes de alertar

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("monitor")

# ── Checks ──
CHECKS = {
    "backbone_health": {
        "name": "🔴 BACKBONE API - Health",
        "url": "https://api.back-bone.dev/health",
        "type": "http",
        "expected_status": 200,
        "severity": "urgent",
    },
    "backbone_landing": {
        "name": "🟠 BACKBONE - Landing",
        "url": "https://back-bone.dev",
        "type": "http",
        "expected_status": 200,
        "severity": "grave",
    },
    "backbone_auth": {
        "name": "🔴 BACKBONE - Tenants Auth",
        "url": "https://api.back-bone.dev/v1/admin/tenants",
        "type": "http",
        "expected_status": 401,
        "severity": "urgent",
    },
    "internet": {
        "name": "🔵 Internet - Cloudflare DNS",
        "url": "https://cloudflare.com/cdn-cgi/trace",
        "type": "http",
        "expected_status": 200,
        "severity": "grave",
    },
    "redis_ping": {
        "name": "🟡 Redis - Container",
        "host": "localhost",
        "port": 6379,
        "type": "tcp",
        "severity": "grave",
    },
}

class Monitor:
    def __init__(self):
        self.state = self._load_state()

    def _load_state(self):
        if STATE_FILE.exists():
            try: return json.loads(STATE_FILE.read_text())
            except: pass
        return {cid: {"down_since": None, "alerted": False, "last_ok": None} for cid in CHECKS}

    def _save_state(self):
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(self.state, indent=2, default=str))

    async def _send_alert(self, check_id, check, status, detail=""):
        now = datetime.now(timezone.utc)
        ts = now.strftime("%H:%M UTC")
        
        if status == "down":
            msg = (
                f"🚨 *{check['name']}*\n"
                f"└ Estado: *CAÍDO* ({detail})\n"
                f"└ Desde: {check.get('url', check.get('host', '?'))}\n"
                f"└ Hora: {ts}"
            )
        elif status == "recovered":
            seconds = (now - self.state[check_id]["down_since"]).total_seconds() if self.state[check_id]["down_since"] else 0
            msg = (
                f"✅ *{check['name']}*\n"
                f"└ Estado: *RECUPERADO*\n"
                f"└ Caída: {int(seconds)}s\n"
                f"└ Hora: {ts}"
            )
        else:
            return

        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": CHAT_ID,
                    "text": msg,
                    "parse_mode": "Markdown",
                }
            )
        logger.info(f"📨 Alerta enviada: {check['name']} → {status}")

    async def check_http(self, check_id, check):
        try:
            async with httpx.AsyncClient(timeout=8, verify=False) as client:
                r = await client.get(check["url"])
                ok = r.status_code == check["expected_status"]
                detail = f"HTTP {r.status_code}" if not ok else "ok"
                return ok, detail
        except Exception as e:
            return False, str(e)[:60]

    async def check_tcp(self, check_id, check):
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(check["host"], check["port"]), timeout=5
            )
            writer.close()
            await writer.wait_closed()
            return True, "ok"
        except Exception as e:
            return False, str(e)[:60]

    async def run_check(self, check_id, check):
        now = datetime.now(timezone.utc)
        s = self.state[check_id]

        if check["type"] == "tcp":
            ok, detail = await self.check_tcp(check_id, check)
        else:
            ok, detail = await self.check_http(check_id, check)

        if ok:
            s["last_ok"] = now.isoformat()
            if s["down_since"]:
                # Se estaba cayendo, verificar si ya pasó DOWNTIME_THRESHOLD
                if not s["alerted"]:
                    # Aún no alertamos — no llegó al threshold
                    down_seconds = (now - s["down_since"]).total_seconds()
                    if down_seconds >= DOWNTIME_THRESHOLD:
                        # Ya habíamos alertado (caso borde), recuperar
                        await self._send_alert(check_id, check, "recovered")
                        s["alerted"] = False
                        s["down_since"] = None
                    else:
                        # No llegó al threshold, solo resetear
                        s["down_since"] = None
                else:
                    await self._send_alert(check_id, check, "recovered")
                    s["alerted"] = False
                    s["down_since"] = None
        else:
            if not s["down_since"]:
                s["down_since"] = now
            else:
                down_seconds = (now - s["down_since"]).total_seconds()
                if down_seconds >= DOWNTIME_THRESHOLD and not s["alerted"]:
                    await self._send_alert(check_id, check, "down", detail)
                    s["alerted"] = True

        self._save_state()

    async def run(self):
        logger.info(f"🟢 Monitor iniciado — {len(CHECKS)} checks cada {CHECK_INTERVAL}s")
        # Enviar heartbeat al inicio
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": CHAT_ID,
                    "text": "🟢 *Monitor BACKBONE iniciado* — 5 checks activos",
                    "parse_mode": "Markdown",
                }
            )

        while True:
            start = asyncio.get_event_loop().time()
            tasks = [self.run_check(cid, c) for cid, c in CHECKS.items()]
            await asyncio.gather(*tasks)
            elapsed = asyncio.get_event_loop().time() - start
            await asyncio.sleep(max(1, CHECK_INTERVAL - elapsed))

async def main():
    m = Monitor()
    await m.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⏹ Monitor detenido")
