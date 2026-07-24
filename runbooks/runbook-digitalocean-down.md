# Runbook: VPS DigitalOcean / Servidor Inaccesible

**Propósito:** Recuperar el servidor si DigitalOcean sufre una caída o el droplet se vuelve inaccesible.
**Tiempo objetivo de recuperación:** 1-4 horas
**Prioridad:** 🟡 Alta — Sin servidor, el ecosistema completo está caído

---

## Síntomas

- SSH no responde (timeout o "connection refused")
- Todos los sitios web del ecosistema caídos
- Dashboard DigitalOcean muestra droplet "off", "locked", o "archived"
- Error: "No route to host"

---

## Paso 1 — Verificar desde dashboard DigitalOcean (5 min)

```bash
# Verificar conectividad mínima
ping -c 3 <IP_DEL_VPS>
# Si no responde: el droplet puede estar apagado o la red caída

# Verificar desde dashboard:
# 1. Ir a cloud.digitalocean.com → Droplets
# 2. ¿El droplet existe? ¿Está power on?
# 3. ¿Hay billing issues? (tarjeta vencida → droplet se apaga automáticamente)
# 4. ¿Resource alerts? (CPU/memoria al 100% sostenido → kernel panic)
```

## Paso 2 — Intentar recuperación desde dashboard (10 min)

### Si el droplet está "off":
```
Dashboard → Droplet → Power → Power On
Esperar 2-3 minutos
SSH al servidor
```

### Si el droplet está "locked":
```
Dashboard → Billing → Update payment method
# Stripe puede haber fallado al cobrar
# Actualizar tarjeta → unlock del droplet
```

### Si el droplet responde pero SSH no:
```
Dashboard → Droplet → Access → Recovery Console
# Iniciar sesión vía consola web
# Verificar: systemctl status sshd, firewall rules, /var/log/auth.log
```

## Paso 3 — Si el droplet está caído sin recuperación (30 min - 4 hrs)

### Opción A: Crear droplet desde snapshot (si existe)
```bash
# 1. Dashboard → Snapshots → Elegir el más reciente
# 2. "Create Droplet" desde snapshot
# 3. Esperar aprovisionamiento (3-5 min)
# 4. Asignar IP flotante (si configurada)
# 5. Verificar servicios
ssh root@<NUEVA_IP>
systemctl status backbone-api caddy cloudflared
```

### Opción B: Restaurar desde backups locales a droplet nuevo
```bash
# 1. Crear droplet nuevo con misma región (NYC3) y specs
# 2. Instalar Docker
sudo apt update && sudo apt install -y docker.io docker-compose

# 3. Clonar workspace desde GitHub/Codeberg
git clone git@github.com:Trogloautoegocrata/workspace.git

# 4. Restaurar .env desde ~/hermes-data/secrets/
cp ~/hermes-data/secrets/backbone-creds-backup.txt projects/BACKBONE/.env

# 5. Iniciar servicios
cd projects/BACKBONE
source .venv/bin/activate
# Iniciar BACKBONE API + dependencias

# 6. Restaurar PostgreSQL
# pg_dump más reciente (de backup local o R2)
# psql -U postgres -d backbone < backup_latest.sql

# 7. Reconfigurar Cloudflare Tunnel
cloudflared tunnel login
cloudflared tunnel create hermes-cloudflare-v4
# Actualizar Dashboard con nuevo token

# 8. Verificar
curl -s http://localhost:8005/health
```

### Opción C: Migración a Hetzner de emergencia
Si DigitalOcean está caído globalmente (raro pero posible):
```
1. Crear servidor en Hetzner (región EU o US)
2. Seguir Pasos de Opción B
3. Actualizar DNS a la IP de Hetzner
```

---

## Paso 4 — Post-recuperación (30 min)

```bash
# 1. Verificar todos los servicios
systemctl status backbone-api --no-pager
systemctl status cloudflared --no-pager
docker ps

# 2. Verificar endpoints
curl -s http://localhost:8005/health
curl -s http://localhost:8081/  # Caddy

# 3. Verificar tunnel
cloudflared tunnel list

# 4. Verificar desde internet
curl -s https://back-bone.dev/health
curl -s https://visionnorth.mx/

# 5. Actualizar IP en runbook si cambió
echo "Nueva IP: $(curl -s https://api.ipify.org)"
```

---

## Backups disponibles

| Tipo | Ubicación | Frecuencia | Antigüedad máxima |
|---|---|---|---|
| **PostgreSQL (local)** | `/home/polaris/.../backups/` | Diario (pg_dump) | 24 horas |
| **Código fuente** | GitHub / Codeberg | Tiempo real | Minutos |
| **.env/credenciales** | `~/hermes-data/secrets/` | Manual | Variable |
| **Configuraciones** | Workspace (git) | Manual | Variable |
| **Cloudflare R2** | 🔲 Pendiente de configurar | — | — |

---

## Datos del servidor

| Campo | Valor |
|---|---|
| **Proveedor** | DigitalOcean |
| **Región** | NYC3 (Nueva York) |
| **IP Pública** | `curl -s https://api.ipify.org` |
| **Especificación** | 8 vCPU, 16 GB RAM, 464 GB SSD |
| **SO** | Ubuntu 22.04 / Linux 6.8 |
| **Servicios clave** | BACKBONE API (:8005), PostgreSQL (:5432), Redis (:6379), Caddy (:8081) |

**Última actualización:** 23-Jul-2026
