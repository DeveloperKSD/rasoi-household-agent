"""WhatsApp adapter (Twilio WhatsApp API / sandbox). Uses plain httpx, so no new dependency.

Real mode needs TWILIO_ACCOUNT_SID + TWILIO_AUTH_TOKEN + TWILIO_WHATSAPP_FROM (and USE_MOCKS=false).
Mock mode never calls Twilio: send() just returns {"mock": True, ...} and webhook signatures are not enforced,
so you can test the whole flow locally with curl.
"""
import os, base64, hashlib, hmac
from xml.sax.saxutils import escape
import httpx
from integrations import common

REQUIRED = ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_WHATSAPP_FROM")


def is_mock() -> bool:
    return common.use_mocks(*REQUIRED)


def allowed_numbers() -> set[str]:
    raw = os.getenv("WHATSAPP_ALLOWED_NUMBERS", "")
    return {n.strip() for n in raw.split(",") if n.strip()}


def is_allowed(sender: str) -> bool:
    allow = allowed_numbers()
    if allow:
        return sender in allow
    return is_mock()  # real mode with an empty allow-list = nobody (messages can approve payments)


def valid_signature(url: str, form: dict, signature: str) -> bool:
    """Twilio: base64(HMAC-SHA1(auth_token, url + sorted(key+value)...))."""
    if is_mock():
        return True
    data = url + "".join(f"{k}{form[k]}" for k in sorted(form))
    mac = hmac.new(os.environ["TWILIO_AUTH_TOKEN"].encode(), data.encode(), hashlib.sha1).digest()
    return hmac.compare_digest(base64.b64encode(mac).decode(), signature or "")


def twiml(text: str) -> str:
    return f"<?xml version='1.0' encoding='UTF-8'?><Response><Message>{escape(text)}</Message></Response>"


async def send(to: str, body: str) -> dict:
    """Proactive outbound message (optional; replies to inbound messages use twiml())."""
    if is_mock():
        print(f"[whatsapp mock] -> {to}: {body}")
        return {"mock": True, "to": to, "body": body}
    sid = os.environ["TWILIO_ACCOUNT_SID"]
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                         auth=(sid, os.environ["TWILIO_AUTH_TOKEN"]),
                         data={"From": os.environ["TWILIO_WHATSAPP_FROM"], "To": to, "Body": body})
        r.raise_for_status()
        return r.json()
