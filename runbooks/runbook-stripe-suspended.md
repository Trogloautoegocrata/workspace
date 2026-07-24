# Runbook: Stripe Suspende Cuenta

**Propósito:** Recuperar capacidad de cobro si Stripe suspende o restringe la cuenta.
**Tiempo objetivo de recuperación:** 1-4 horas (transferencia bancaria)
**Prioridad:** 🟡 Alta — Sin Stripe no podemos cobrar suscripciones

---

## Síntomas

- Pagos fallan con `card_declined` genérico incluso con tarjetas válidas
- Dashboard Stripe muestra "account restricted" o "action required"
- Email de Stripe: "We need more information" / "Account review required"
- Webhooks de Stripe dejan de llegar

---

## Paso 1 — No entrar en pánico (5 min)

Stripe normalmente suspende por una de estas razones:

| Causa | Síntoma | Tiempo típico de resolución |
|---|---|---|
| KYC incompleto | "Verify your business information" | 1-3 días |
| Chargebacks > 1% | "High dispute rate" | 1-2 semanas (plan de remediación) |
| Actividad inusual | "Unusual volume spike" | 24-48 horas |
| Documentación vencida | "ID/document expired" | 1-3 días |
| Términos violados | "Prohibited business" | Días a semanas |

## Paso 2 — Verificar estado (10 min)

```bash
# 1. Verificar el estado de la cuenta desde el .env
cd /home/polaris/workspace/projects/BACKBONE

# 2. Obtener la API key del .env
grep "^STRIPE_API_KEY\|^STRIPE_SECRET_KEY" .env

# 3. Verificar balance y estado
source .venv/bin/activate
python3 -c "
import stripe
from dotenv import load_dotenv
import os
load_dotenv()
stripe.api_key = os.getenv('STRIPE_API_KEY', os.getenv('STRIPE_SECRET_KEY', ''))
try:
    bal = stripe.Balance.retrieve()
    print(f'Balance disponible: {sum(a.amount for a in bal.available) / 100:.2f} USD')
    print(f'Balance pendiente: {sum(a.amount for a in bal.pending) / 100:.2f} USD')
except Exception as e:
    print(f'Error accediendo a Stripe: {e}')
    print('→ La cuenta puede estar restringida')
"
```

## Paso 3 — Notificar a clientes (15 min)

Si hay clientes activos y Stripe está caído:

**Email template:**

> **Asunto:** Actualización en nuestro sistema de pagos
>
> Estimado cliente,
>
> Estamos realizando una actualización en nuestro sistema de pagos.
> Tu servicio continúa activo sin interrupciones.
>
> En las próximas 24-48 horas recibirás instrucciones para actualizar
> tu método de pago.
>
> Para cualquier duda, responde a este correo.
>
> — El equipo de BACKBONE

## Paso 4 — Activar fallback (1-4 horas)

### Opción A: Transferencia bancaria directa ✅ RECOMENDADO

| Ventaja | Desventaja |
|---|---|
| Inmediato, sin aprobación de terceros | Manual, requiere seguimiento |
| Sin comisiones | El cliente debe iniciar la transferencia |

**Datos para compartir con el cliente:**
```
Beneficiario: CAMARENA'S GROUP LLC
Banco: [Banco de la LLC — verificar]
Cuenta: [Cuenta de la LLC — verificar]
Routing: [Routing number — verificar]
SWIFT: [SWIFT code — verificar]
Concepto: "BACKBONE API — [nombre del cliente]"
Monto: [monto en USD]
```

### Opción B: PayPal (futuro — pendiente de configurar)

- Comisión: 2.99% + $0.49 USD por transacción
- Configuración: 1-2 horas en dashboard PayPal
- No requiere documentación empresarial extensa

### Opción C: MercadoPago (futuro — pendiente de configurar)

- Ideal para pagos en México (OXXO, SPEI, tarjetas MX)
- Comisión: ~3-4% por transacción
- Configuración: 1-2 días (requiere RFC y documentación)
- **Proyecto para Q4 2026**

## Paso 5 — Resolver con Stripe

```bash
# 1. Ir a: https://dashboard.stripe.com/support
# 2. Seleccionar "Account" → "Account review / restriction"
# 3. Tener listo:
```

**Documentación requerida típicamente:**
- [ ] EIN/ITIN de CAMARENA'S GROUP LLC
- [ ] Certificado de Incorporación (NM Secretary of State)
- [ ] Estados financieros básicos (Profit & Loss)
- [ ] Lista de clientes (con permiso de Stripe para contactarlos)
- [ ] Descripción del negocio en 1 párrafo
- [ ] URL del sitio web del producto (back-bone.dev)
- [ ] Términos de servicio publicados

**Texto sugerido para el ticket:**
> "CAMARENA'S GROUP LLC (EIN: 36-5125625) operates BACKBONE API,
> a real estate data platform for Mexico. We provide property data
> via REST API to real estate professionals. Our business model is
> B2B SaaS subscriptions ($99-$4,999/mo). We have [N] active
> subscribers and our chargeback rate is [X]%. Our website is
> back-bone.dev and our terms are at back-bone.dev/terms."

---

## Contactos

| Canal | Detalle |
|---|---|
| **Dashboard Stripe** | dashboard.stripe.com → Support |
| **Email Stripe** | A través del dashboard (no hay email directo público) |
| **MercadoPago MX** | Soporte desde dashboard.mercadopago.com.mx |

---

## Datos de la cuenta

| Campo | Valor |
|---|---|
| **Entidad legal** | CAMARENA'S GROUP LLC |
| **EIN** | 36-5125625 |
| **Estado de incorporación** | Nuevo México, EE.UU. |
| **Fecha de incorporación** | 27-Nov-2024 |
| **Entity ID** | 7942303 |

**Última actualización:** 23-Jul-2026
