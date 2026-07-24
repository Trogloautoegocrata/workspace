# Runbook: Cloudflare Tunnel Caído

**Propósito:** Recuperar acceso al ecosistema cuando Cloudflare Tunnel deja de funcionar.
**Tiempo objetivo de recuperación:** 30 minutos
**Prioridad:** 🔴 Alta — Sin tunnel, el ecosistema completo es inaccesible (27 rutas)

---

## Síntomas

- 502/503/521 en todos los subdominios servidos por tunnel
- `cloudflared tunnel list` muestra "disconnected" o "degraded"
- Dashboard Cloudflare Zero Trust → Networks → Tunnels muestra status rojo

---

## Paso 1 — Verificar estado (2 min)

```bash
# Ver estado del servicio cloudflared
sudo systemctl status cloudflared --no-pager

# Ver lista de túneles y su estado
cloudflared tunnel list

# Ver información del túnel específico
cloudflared tunnel info hermes-cloudflare-v4

# Verificar conectividad a internet desde el servidor
curl -s https://api.ipify.org
```

## Paso 2 — Intentar reconexión (5 min)

```bash
# Opción A: Reiniciar el servicio (reconecta automáticamente)
sudo systemctl restart cloudflared

# Esperar 10 segundos
sleep 10

# Verificar si reconectó
sudo systemctl status cloudflared --no-pager
cloudflared tunnel list

# Opción B: Si sigue desconectado, forzar re-autenticación del túnel
cloudflared tunnel login
# → Se abrirá un link. Autenticar en el navegador y pegar el token.

# Opción C: Recrear el archivo de configuración del túnel
cloudflared tunnel delete hermes-cloudflare-v4
cloudflared tunnel create hermes-cloudflare-v4
# → Copiar el nuevo token y actualizar la ruta en el Dashboard
```

## Paso 3 — Si el tunnel no reconecta (fallback de emergencia)

**⚠️ ADVERTENCIA:** Este paso EXPONE la IP real del VPS.
Solo usar si el tiempo de recuperación es crítico y el riesgo es aceptable.

```bash
# 1. Obtener IP pública del servidor
SERVER_IP=$(curl -s https://api.ipify.org)
echo "IP del servidor: $SERVER_IP"

# 2. Configurar firewall restrictivo ANTES de exponer
sudo ufw default deny incoming
sudo ufw allow ssh
sudo ufw allow from your-home-ip to any port 80,443
sudo ufw enable

# 3. Ir al Dashboard de Cloudflare → DNS → Registros
# Cambiar los registros A de proxy activo (naranja) a solo DNS (gris)
# api.back-bone.dev → A → $SERVER_IP (DNS only)
# back-bone.dev → A → $SERVER_IP (DNS only)
# Esperar propagación (~1-5 min)

# 4. Verificar que el VPS responde en HTTP/HTTPS
curl -s -o /dev/null -w "%{http_code}" http://$SERVER_IP/
```

## Paso 4 — Contactar soporte Cloudflare

| Canal | Detalle |
|---|---|
| **Dashboard** | one.dash.cloudflare.com → ? → Help → Contact Support |
| **Email** | support@cloudflare.com |
| **Plan actual** | Free — sin prioridad. Esperar 1-4 horas. |

**Información que tener lista:**
- Tunnel ID: `hermes-cloudflare-v4`
- Nombres de dominio afectados: todos los subdominios de visionnorth.mx, polaris.pw, back-bone.dev, enmexico.casa
- IP del servidor: (obtener con `curl -s https://api.ipify.org`)
- Último commit del túnel: `cloudflared tunnel list`

---

## Paso 5 — Restaurar tunnel cuando Cloudflare responda

```bash
# 1. Revertir registros DNS a proxy activo (naranja) en Dashboard
# 2. Reactivar tunnel
sudo systemctl restart cloudflared
sleep 10
sudo systemctl status cloudflared --no-pager

# 3. Deshabilitar firewall de emergencia
sudo ufw disable

# 4. Verificar que todo funciona via tunnel
curl -s https://back-bone.dev/health
```

---

## Prevención

- **Monitoreo:** Configurar un health check externo (Uptime Kuma, Better Uptime) que alerte si el tunnel cae
- **DNS backup:** Tener los registros A con la IP del servidor listos pero desactivados (proxy on), para activarlos rápido si es necesario
- **Documentación:** Mantener este runbook actualizado con la IP actual del servidor

---

## IPs del servidor

| Tipo | Valor |
|---|---|
| Pública | `curl -s https://api.ipify.org` |
| Local | 127.0.0.1 |

**Última actualización:** 23-Jul-2026
