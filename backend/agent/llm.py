"""LLM is used for judgement (meal choice + explanation, voice interpretation) inside guard-rails.
Deterministic code validates every LLM output. No API key => deterministic fallbacks."""
import os, re, json
from datetime import date, timedelta

MODEL = os.getenv("LLM_MODEL", "claude-sonnet-5-5")


def _ask(system, payload, max_tokens=400):
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return None
    try:
        import anthropic
        msg = anthropic.Anthropic(api_key=key).messages.create(
            model=MODEL, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": json.dumps(payload, default=str)}])
        text = "".join(b.text for b in msg.content if b.type == "text")
        m = re.search(r"\{.*\}", text, re.S)
        return json.loads(m.group(0)) if m else None
    except Exception:
        return None


def choose_meal(summary, candidates):
    """Returns {'meal_id', 'reason'} or None. Candidates are already constraint-checked."""
    slim = [{"meal_id": c["id"], "name": c["name"], "score": c["score"], "reasons": c["reasons"],
             "missing_items": len(c["missing"]), "cost": c["cost_estimate"], "protein_g": c["protein"]}
            for c in candidates[:5]]
    out = _ask("You are Rasoi, a household meal-planning agent. Choose exactly ONE meal_id from the candidates "
               "(all already satisfy hard constraints). Prefer using ingredients that expire soon, meeting the "
               "nutrition goal, and avoiding recent repeats. Reply with ONLY JSON: "
               '{"meal_id": <int>, "reason": "<one sentence>"}', {"household": summary, "candidates": slim})
    if out and any(c["id"] == out.get("meal_id") for c in candidates):
        return {"meal_id": out["meal_id"], "reason": str(out.get("reason", ""))[:300]}
    return None


NEG = ("mat", "nahi", "nako", "nahin", "don't", "dont", "do not", "avoid", "without", "no ")


def interpret_voice(transcript, known_ingredients):
    today = date.today()
    out = _ask("Interpret a household member's voice note (Hindi/Marathi/English/Hinglish). Reply with ONLY JSON: "
               '{"intent": "exclude_ingredient"|"unknown", "ingredient": "<one of known_ingredients or null>", '
               '"date": "YYYY-MM-DD or null", "summary": "<short English paraphrase>"}. '
               '"kal" means tomorrow, "aaj" today, "parso" day after tomorrow.',
               {"today": today.isoformat(), "transcript": transcript, "known_ingredients": known_ingredients})
    if out and out.get("intent") == "exclude_ingredient" and out.get("ingredient") in known_ingredients:
        return {**out, "via": "llm"}
    # regex fallback
    t = transcript.lower()
    ing = next((i for i in known_ingredients if i in t), None)
    if ing and any(n in t for n in NEG):
        d = today + timedelta(days=2 if "parso" in t else 0 if "aaj" in t else 1)
        return {"intent": "exclude_ingredient", "ingredient": ing, "date": d.isoformat(),
                "summary": f"Do not cook with {ing} on {d.isoformat()}", "via": "regex"}
    return {"intent": "unknown", "ingredient": None, "date": None, "summary": "Could not interpret", "via": "regex"}
