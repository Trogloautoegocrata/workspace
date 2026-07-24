# Runbook: Caída de Redis

## Síntomas
- BACKBONE API responde lento
- Rate limiting deshabilitado (fallback a DB directo)
- Cache miss en todas las consultas
- Health check marca "redis: unreachable"

## Diagnóstico
```bash
# Verificar estado del contenedor
docker ps | grep backbone-redis

# Verificar logs
docker logs backbone-redis --tail 50

# Probar conexión directa
redis-cli -h localhost -p 6379 -a backbone_redis_dev ping
```

## Recuperación
```bash
# Si el contenedor está caído pero no eliminado
docker start backbone-redis

# Si el contenedor no existe, recrear
docker run -d \
  --name backbone-redis \
  --restart unless-stopped \
  -p 127.0.0.1:6379:6379 \
  -v backbone-redis-data:/data \
  redis:7-alpine \
  redis-server --requirepass backbone_redis_dev

# Verificar que la API lo detecta
curl -s http://localhost:8005/health | python3 -c "import sys,json; print(json.load(sys.stdin).get('redis','unknown'))"
```

## Notas
- Redis es un singleton. No hay clustering configurado.
- La API tiene degradación graceful: sin Redis, consulta DB directo con límites conservadores.
- La contraseña está en .env como REDIS_PASSWORD
- Puerto solo local (127.0.0.1:6379), no expuesto al público
