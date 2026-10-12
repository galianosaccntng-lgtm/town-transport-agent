# Agente virtual para WhatsApp (Cloud API)

Servidor que recibe los mensajes de tus clientes por la API oficial de WhatsApp
(Cloud API de Meta) y responde automáticamente con la información de tu compañía.

## Cómo funciona

1. Un cliente escribe a tu número de WhatsApp Business.
2. Meta envía el mensaje a este servidor (webhook).
3. El agente busca la respuesta en `knowledge.json` (precios, horarios, envíos…).
4. El servidor responde al cliente por la Cloud API, todo en segundos.

## Puesta en marcha

### Fase 1 — Cuentas en Meta (gratis)

1. Entra a [developers.facebook.com](https://developers.facebook.com) e inicia sesión
   con tu cuenta de Facebook. Crea tu cuenta de desarrollador (es gratis).
2. **My Apps → Create App** → tipo **Business** → ponle un nombre (ej. "Agente WhatsApp").
3. Dentro del dashboard de la app: **Add Product → WhatsApp → Set up**.
4. Meta te da al instante un **número de prueba gratuito** y un **token temporal**.
   Anota dos valores de la página "API Setup":
   - **Phone Number ID** (un número largo; no es el número de teléfono en sí)
   - **Access token** (temporal, dura ~24 h; sirve para probar hoy)

Con esto ya puedes enviarte mensajes de prueba: agrega tu número personal como
destinatario verificado (hasta 5 números) en la misma página.

### Fase 2 — Token permanente (para no renovarlo cada día)

1. Ve a [business.facebook.com](https://business.facebook.com) → **Configuración del negocio**
   (engranaje) → **Usuarios → Usuarios del sistema** → **Añadir** (nombre ej. "API WhatsApp",
   rol Administrador).
2. Selecciónalo → **Añadir activos** → elige tu app y tu cuenta de WhatsApp →
   dale **Control total** → Guardar.
3. **Generar nuevo token** → elige tu app → marca `whatsapp_business_messaging` y
   `whatsapp_business_management` → caducidad **Nunca** → Generar.
4. **Copia el token ahora** (solo se muestra una vez). Guárdalo en un lugar seguro.

### Fase 3 — Configurar este proyecto

```bash
cd whatsapp-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edita `.env`:

```
VERIFY_TOKEN=un-texto-secreto-largo-que-inventes-tu
WHATSAPP_TOKEN=el-token-permanente-de-la-fase-2
PHONE_NUMBER_ID=el-phone-number-id-de-la-fase-1
```

Edita `knowledge.json` con los datos reales de tu compañía (nombre, horarios,
precios, zonas de entrega, preguntas frecuentes). El agente responde con eso
sin que toques código.

Prueba local (modo DRY-RUN, sin enviar mensajes reales):

```bash
uvicorn app:app --port 8000
# En otra terminal:
curl "http://localhost:8000/webhook?hub.mode=subscribe&hub.verify_token=TU_TOKEN&hub.challenge=123"
# Debe devolver: 123
```

### Fase 4 — Publicar el servidor en internet

Meta necesita una URL pública **HTTPS** para el webhook. Opciones:

- **Fácil (1 clic):** Render — este proyecto ya incluye `Dockerfile` y `render.yaml`.
  Sube la carpeta a un repositorio de GitHub y en Render elige "New → Blueprint",
  pega la URL del repo y listo. Render te pedirá los valores del `.env`
  (VERIFY_TOKEN, WHATSAPP_TOKEN, etc.) en su panel seguro.
- **Otras opciones:** Railway o Fly.io (despliegue desde Git en minutos).
- **VPS propio:** cualquier servidor con Docker o Python + certificado HTTPS.
- **Solo para probar hoy:** [ngrok](https://ngrok.com) → `ngrok http 8000`
  te da una URL temporal `https://xxxx.ngrok.io`.

La URL del webhook será: `https://tu-dominio/webhook`

### Fase 5 — Conectar el webhook en Meta

1. En tu app: **WhatsApp → Configuration → Webhook → Edit**.
2. **Callback URL:** `https://tu-dominio/webhook`
3. **Verify token:** el mismo `VERIFY_TOKEN` de tu `.env`.
4. **Verify and Save** (Meta llama a tu servidor para confirmar).
5. En **Webhook fields → Manage**, suscríbete al campo **`messages`**.

### Fase 6 — Probar de verdad

Escríbele al número de prueba desde tu WhatsApp personal (agregado como
destinatario verificado). El agente debe responder con tu mensaje de bienvenida.
Revisa los logs del servidor para ver cada mensaje y respuesta.

### Fase 7 — Pasar a producción

- Registra tu **número real del negocio** en la plataforma (no puede estar en uso
  en la app de WhatsApp al mismo tiempo; usa un número dedicado).
- Completa la **verificación del negocio** en Meta para escribirle al público general.
- Recuerda la **ventana de 24 horas**: puedes responder libremente dentro de las
  24 h del último mensaje del cliente; fuera de ella se usan plantillas aprobadas.
- Meta incluye 1,000 mensajes de servicio gratis al mes por cuenta.

## Seguridad

- Nunca compartas `WHATSAPP_TOKEN` por chat ni lo subas a git (`.env` ya está
  pensado para quedar fuera del repositorio).
- Cambia `VERIFY_TOKEN` por un valor largo y aleatorio.
- En producción, sirve la app detrás de HTTPS y considera validar la firma
  `X-Hub-Signature-256` de Meta con tu App Secret.

## Archivos

| Archivo           | Qué es                                                        |
|-------------------|---------------------------------------------------------------|
| `app.py`          | Servidor FastAPI: webhooks de WhatsApp y Messenger + envío     |
| `agent.py`        | Lógica del agente: saludo → FAQ por palabras clave → humano    |
| `knowledge.json`  | **Edítalo**: datos de tu compañía y respuestas                  |
| `.env.example`    | Plantilla de credenciales (copiar a `.env`)                    |
| `requirements.txt`| Dependencias Python                                            |

## Messenger (bot en tu Página de Facebook)

Sí: el mismo servidor y el mismo agente pueden atender Messenger. Solo cambia
la configuración en Meta; el código ya trae los endpoints `/webhook/messenger`.

1. **Crea una Página de Facebook** para Town Transport LLC (si no tienes):
   [facebook.com/pages/create](https://www.facebook.com/pages/create).
2. En tu misma app de Meta: **Add Product → Messenger → Set up**.
3. **Messenger → Settings → Add or Remove Pages** → elige tu página →
   **Generate token** → cópialo como `PAGE_ACCESS_TOKEN` en tu `.env`.
4. **Messenger → Settings → Webhooks → Add Callback URL**:
   - Callback URL: `https://tu-dominio/webhook/messenger`
   - Verify token: tu `MESSENGER_VERIFY_TOKEN` (puede ser el mismo `VERIFY_TOKEN`)
   - **Verify and Save**, y suscríbete al campo **`messages`**
     (opcional: también `messaging_postbacks`).
5. Prueba: envíale un mensaje a tu Página desde otra cuenta de Facebook.
6. Para uso público: pon la app en modo **Live** y agrega una **Privacy Policy URL**
   en App Settings → Basic (requerido por Meta).

Notas:
- El bot responde en el chat de tu Página, con la misma base de conocimiento
  (`knowledge.json`) que WhatsApp: editas un solo archivo para ambos canales.
- Messenger no cobra por mensaje como WhatsApp; la ventana de respuesta es de
  24 horas desde el último mensaje del cliente (política de Meta).
