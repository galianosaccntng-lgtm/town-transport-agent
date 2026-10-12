"""Servidor webhook para el agente virtual de WhatsApp (Cloud API).

- GET  /webhook : verificación que hace Meta al configurar el webhook.
- POST /webhook : recibe mensajes entrantes y responde con el agente virtual.
- GET  /health  : comprobación simple de que el servidor está vivo.

Configuración por variables de entorno (ver .env.example):
  VERIFY_TOKEN     Token que TÚ inventas; debe coincidir con el que pongas en Meta.
  WHATSAPP_TOKEN   Token de acceso de la Cloud API (temporal para pruebas o permanente).
  PHONE_NUMBER_ID  ID del número de teléfono (no el número en sí).
  GRAPH_VERSION    Versión de la Graph API (por defecto v21.0).

Si faltan WHATSAPP_TOKEN o PHONE_NUMBER_ID, el servidor corre en modo
DRY-RUN: procesa los mensajes y muestra la respuesta en el log sin enviarla.
Útil para probar la lógica del agente sin credenciales.
"""

import logging
import os

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse

from agent import load_knowledge, make_reply

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("whatsapp-agent")

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID", "")
GRAPH_VERSION = os.getenv("GRAPH_VERSION", "v21.0")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KNOWLEDGE = load_knowledge(os.path.join(BASE_DIR, "knowledge.json"))

app = FastAPI(title="Agente virtual WhatsApp")


@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/webhook")
async def verify_webhook(request: Request):
    """Handshake de verificación de Meta: responde el challenge si el token coincide."""
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge", "")
    if mode == "subscribe" and token and token == VERIFY_TOKEN:
        log.info("Webhook verificado por Meta.")
        return PlainTextResponse(content=challenge)
    log.warning("Intento de verificación con token inválido.")
    return Response(status_code=403)


@app.post("/webhook")
async def receive_webhook(request: Request):
    """Recibe notificaciones de mensajes y responde con el agente virtual."""
    try:
        data = await request.json()
    except Exception:
        log.exception("Cuerpo del webhook no es JSON válido.")
        return {"status": "ok"}

    try:
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                for msg in value.get("messages", []):
                    if msg.get("type") != "text":
                        continue
                    sender = msg.get("from", "")
                    body = msg.get("text", {}).get("body", "")
                    if not sender or not body:
                        continue
                    log.info("Mensaje de %s: %s", sender, body)
                    reply = make_reply(body, KNOWLEDGE)
                    await send_text(sender, reply)
    except Exception:
        log.exception("Error procesando el webhook.")

    # Siempre responder 200 para que Meta no reintente de más.
    return {"status": "ok"}


async def send_text(to: str, text: str) -> None:
    """Envía un mensaje de texto por la Cloud API (o simula si faltan credenciales)."""
    if not WHATSAPP_TOKEN or not PHONE_NUMBER_ID:
        log.warning("DRY-RUN (sin credenciales). Respuesta para %s:\n%s", to, text)
        return

    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{PHONE_NUMBER_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(url, json=payload, headers=headers)
        if r.status_code >= 400:
            log.error("Error enviando mensaje (%s): %s", r.status_code, r.text)
        else:
            log.info("Respuesta enviada a %s", to)
    except Exception:
        log.exception("Fallo de red enviando mensaje a %s", to)


# ---------------------------------------------------------------------------
# Messenger (Facebook Page) — usa el mismo agente y la misma base de conocimiento
# ---------------------------------------------------------------------------
# Requiere en Meta: una Página de Facebook del negocio conectada a tu app
# (producto Messenger), un Page Access Token y el webhook configurado en:
#   https://tu-dominio/webhook/messenger
# Variables: MESSENGER_VERIFY_TOKEN (o usa VERIFY_TOKEN) y PAGE_ACCESS_TOKEN.

MESSENGER_VERIFY_TOKEN = os.getenv("MESSENGER_VERIFY_TOKEN", VERIFY_TOKEN)
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "")


@app.get("/webhook/messenger")
async def verify_messenger_webhook(request: Request):
    """Handshake de verificación de Meta para el webhook de Messenger."""
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge", "")
    if mode == "subscribe" and token and token == MESSENGER_VERIFY_TOKEN:
        log.info("Webhook de Messenger verificado por Meta.")
        return PlainTextResponse(content=challenge)
    log.warning("Intento de verificación de Messenger con token inválido.")
    return Response(status_code=403)


@app.post("/webhook/messenger")
async def receive_messenger_webhook(request: Request):
    """Recibe mensajes de la Página de Facebook y responde con el agente virtual."""
    try:
        data = await request.json()
    except Exception:
        log.exception("Cuerpo del webhook de Messenger no es JSON válido.")
        return {"status": "ok"}

    try:
        if data.get("object") != "page":
            return {"status": "ok"}
        for entry in data.get("entry", []):
            for event in entry.get("messaging", []):
                sender_id = (event.get("sender") or {}).get("id", "")
                message = event.get("message") or {}
                if message.get("is_echo"):
                    continue  # ignorar ecos de nuestros propios mensajes
                text = message.get("text", "")
                if not sender_id or not text:
                    continue
                log.info("Mensaje de Messenger %s: %s", sender_id, text)
                reply = make_reply(text, KNOWLEDGE)
                await send_messenger_text(sender_id, reply)
    except Exception:
        log.exception("Error procesando el webhook de Messenger.")

    return {"status": "ok"}


async def send_messenger_text(psid: str, text: str) -> None:
    """Envía un mensaje por la Send API de Messenger (o simula si falta el token)."""
    if not PAGE_ACCESS_TOKEN:
        log.warning("DRY-RUN Messenger (sin PAGE_ACCESS_TOKEN). Respuesta para %s:\n%s", psid, text)
        return

    url = f"https://graph.facebook.com/{GRAPH_VERSION}/me/messages"
    params = {"access_token": PAGE_ACCESS_TOKEN}
    payload = {"recipient": {"id": psid}, "message": {"text": text}}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(url, params=params, json=payload)
        if r.status_code >= 400:
            log.error("Error enviando mensaje de Messenger (%s): %s", r.status_code, r.text)
        else:
            log.info("Respuesta de Messenger enviada a %s", psid)
    except Exception:
        log.exception("Fallo de red enviando mensaje de Messenger a %s", psid)
