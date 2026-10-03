"""WhatsApp channel. Purely additive: it only CALLS existing functions (rasoi.start_run / resolve, llm.interpret_voice,
th.add_voice_rule). It does not change the agent, the state machine or the DB schema.

Messages it understands:
  plan | run      start a planning run
  status          where is the latest run / what is it waiting for
  1, 2, 3 ...     pick an option when the agent is waiting for a human
  help
  anything else   treated like a voice note, e.g. "kal paneer mat banana" -> exclude-ingredient rule
"""
import os
from fastapi import APIRouter, Request, Response, HTTPException
from db.database import q, one, J
from db.seed import HID
from agent import rasoi, llm
from agent.rasoi import Run
from tools import household as th
from integrations import whatsapp as wa

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])

HELP = ("Rasoi commands:\n• plan – plan tomorrow's meal\n• status – see the latest run\n"
        "• 1 / 2 / 3 – answer when I ask you to decide\n• or just type a note, e.g. \"kal paneer mat banana\"")


def _household_id() -> str:
    return os.getenv("WHATSAPP_HOUSEHOLD_ID", HID)


def _latest(hid):
    row = one("SELECT run_id FROM agent_runs WHERE household_id=%s ORDER BY created_at DESC LIMIT 1", (hid,))
    return Run.load(row["run_id"]) if row else None


def _status_text(r) -> str:
    if not r:
        return "No runs yet. Send \"plan\" to start one."
    meal = (r.ctx.get("meal") or {}).get("name")
    lines = [f"Run {r.run_id}: {r.status} (step: {r.state})" + (f"\nMeal: {meal}" if meal else "")]
    req = r.ctx.get("human_request")
    if r.status == "NEEDS_HUMAN" and req:
        lines.append(f"\n{req['message']}")
        lines += [f"{i}. {o['label']}" for i, o in enumerate(req["options"], 1)]
        lines.append("\nReply with the number.")
    return "\n".join(lines)


def _handle_choice(r, n: int) -> str:
    req = (r.ctx.get("human_request") if r else None)
    if not r or r.status != "NEEDS_HUMAN" or not req:
        return "I'm not waiting for a decision right now. Send \"status\" to check."
    opts = req["options"]
    if not 1 <= n <= len(opts):
        return f"Please reply with a number from 1 to {len(opts)}."
    opt = opts[n - 1]
    params = {k: v for k, v in opt.items() if k in ("rule_id", "amount")}
    try:
        rasoi.resolve(r.run_id, opt["action"], params)
    except ValueError as e:
        return f"Couldn't do that: {e}"
    return f"Done: {opt['label']}. Continuing…"


def _handle_note(hid, text: str, sender: str) -> str:
    known = [x["ingredient"] for x in q("SELECT ingredient FROM catalog")]
    interp = llm.interpret_voice(text, known)
    rule_id = th.add_voice_rule(hid, interp)
    q("INSERT INTO voice_inputs (household_id,raw_response,transcript,interpretation) VALUES (%s,%s,%s,%s)",
      (hid, J({"channel": "whatsapp", "from": sender}), text, J(interp)))
    if rule_id:
        return f"Got it: {interp['summary']}. I'll apply this to the next plan."
    return "I couldn't turn that into a rule. " + HELP


def handle_message(hid: str, text: str, sender: str) -> str:
    t = text.strip().lower()
    if t in ("help", "hi", "hello", "?"):
        return HELP
    if t in ("plan", "run", "start"):
        cur = _latest(hid)
        if cur and cur.status == "RUNNING":
            return "A run is already in progress. Send \"status\" to follow it."
        return f"Started planning. Run {rasoi.start_run(hid)}. I'll reply to \"status\" any time."
    if t == "status":
        return _status_text(_latest(hid))
    if t.isdigit():
        return _handle_choice(_latest(hid), int(t))
    if not t:
        return HELP
    return _handle_note(hid, text.strip(), sender)


@router.post("/webhook")
async def webhook(request: Request):
    form = dict((await request.form()).items())
    base = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")  # e.g. your ngrok URL; must match what Twilio calls
    url = f"{base}{request.url.path}" if base else str(request.url)
    if not wa.valid_signature(url, form, request.headers.get("X-Twilio-Signature", "")):
        raise HTTPException(403, "bad signature")
    sender = form.get("From", "")
    if not wa.is_allowed(sender):
        return Response(wa.twiml("Sorry, this number isn't linked to a household."), media_type="application/xml")
    try:
        reply = handle_message(_household_id(), form.get("Body", ""), sender)
    except Exception as e:  # never let a bad message turn into a Twilio retry storm
        print("whatsapp handler error:", repr(e))
        reply = "Something went wrong on my side. Please try again."
    return Response(wa.twiml(reply), media_type="application/xml")
