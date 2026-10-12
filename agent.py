"""Lógica del agente virtual: responde usando la base de conocimiento.

Estrategia simple y predecible (sin IA externa):
1. Si el mensaje es un saludo corto -> mensaje de bienvenida de la empresa.
2. Si coincide con palabras clave de una FAQ -> responde esa FAQ.
3. Si no -> mensaje de fallback que deriva a un humano.

Toda la información vive en knowledge.json: edítalo y el agente
responde con tus datos sin tocar código.
"""

import json
import unicodedata


def _norm(text: str) -> str:
    """Minúsculas y sin tildes para comparar sin importar cómo escriba el cliente."""
    text = (text or "").lower()
    text = "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )
    return text


def load_knowledge(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _default_greeting(company: dict) -> str:
    name = company.get("name", "nuestra empresa")
    lines = [
        f"¡Hola! Gracias por escribir a *{name}*. 👋",
    ]
    if company.get("description"):
        lines.append(company["description"])
    lines.append("¿En qué te puedo ayudar? Puedo darte precios, horarios y zonas de entrega.")
    return "\n".join(lines)


def make_reply(text: str, kb: dict) -> str:
    company = kb.get("company", {})
    faqs = kb.get("faqs", []) or []
    msg = _norm(text).strip()

    if not msg:
        return kb.get("fallback", "¿En qué te puedo ayudar?")

    # 1. Saludo corto
    greetings = ["hola", "buenas", "buenos dias", "buenas tardes",
                 "buenas noches", "hello", "hi", "hey"]
    words = msg.split()
    if len(words) <= 4 and any(g in msg for g in greetings):
        return kb.get("greeting") or _default_greeting(company)

    # 2. Mejor FAQ por coincidencia de palabras clave
    best = None
    best_score = 0
    for faq in faqs:
        keywords = faq.get("keywords", []) or []
        score = sum(1 for kw in keywords if _norm(str(kw)) and _norm(str(kw)) in msg)
        if score > best_score:
            best, best_score = faq, score
    if best and best.get("answer"):
        return best["answer"]

    # 3. Fallback: derivar a humano
    return kb.get(
        "fallback",
        "Gracias por tu mensaje. Un asesor te responderá en breve. "
        "¿Me dejas tu nombre para atenderte mejor?",
    )
