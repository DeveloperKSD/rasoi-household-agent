import math
from datetime import date, timedelta
from db.database import q


def find_meals():
    return q("SELECT * FROM meals ORDER BY id")


def availability(items):
    out = {}
    for i in items:
        if not i.get("expired"):
            out[i["ingredient"]] = out.get(i["ingredient"], 0) + i["quantity"]
    return out


def check_constraints(meal, c):
    """Deterministic hard-constraint check. The LLM never overrides this."""
    v = []
    if c["diet"] == "vegetarian" and meal["diet"] != "vegetarian":
        v.append("not vegetarian")
    for x in c["exclude_contains"]:
        if x in (meal["contains"] or []):
            v.append(f"contains {x}")
    names = {i["name"] for i in meal["ingredients"]}
    for x in c["exclude_ingredients"]:
        if x in names:
            v.append(f"uses {x}")
    protein = (meal["nutrition"] or {}).get("protein", 0)
    if c["min_protein"] and protein < c["min_protein"]:
        v.append(f"only {protein}g protein")
    if c["max_meal_cost"] and meal["cost_estimate"] > c["max_meal_cost"]:
        v.append(f"costs ₹{meal['cost_estimate']:.0f}")
    return v


def missing_for(meal, avail):
    out = []
    for i in meal["ingredients"]:
        short = i["quantity"] - avail.get(i["name"], 0)
        if short > 0:
            out.append({"name": i["name"], "quantity": math.ceil(short), "unit": i["unit"]})
    return out


def rank_meals(meals, c, inv_items, recent, prefs, goal, rejected=(), pantry_only=False):
    avail = availability(inv_items)
    by_name = {i["ingredient"]: i for i in inv_items}
    recent_names = {r["name"] for r in recent[:3]}
    prefs_l = {p.lower() for p in prefs}
    candidates, excluded = [], []
    for m in meals:
        if m["id"] in rejected:
            continue
        viol = check_constraints(m, c)
        if viol:
            excluded.append({"meal": m["name"], "violations": viol}); continue
        missing = missing_for(m, avail)
        if pantry_only and missing:
            continue
        score, reasons = 0.0, []
        if c["diet"] == "vegetarian":
            reasons.append("Vegetarian")
        for i in m["ingredients"]:
            it = by_name.get(i["name"])
            if it and it["expires_in_days"] is not None and 0 <= it["expires_in_days"] <= 2 and i["name"] in avail:
                score += 3
                reasons.append(f"{i['name']} expires " + ("tomorrow" if it["expires_in_days"] == 1 else f"in {it['expires_in_days']}d"))
        protein = (m["nutrition"] or {}).get("protein", 0)
        if goal == "high_protein":
            score += protein / 10
            if protein >= 20:
                reasons.append(f"High protein ({protein}g)")
        hits = prefs_l & {t.lower() for t in m["tags"]}
        score += len(hits)
        score -= m["cost_estimate"] / 100
        score -= 0.5 * len(missing)
        if m["name"] in recent_names:
            score -= 2; reasons.append("Cooked recently (penalised)")
        candidates.append({"id": m["id"], "name": m["name"], "score": round(score, 2), "reasons": reasons,
                           "missing": missing, "cost_estimate": m["cost_estimate"], "protein": protein,
                           "ingredients": m["ingredients"], "instructions": m["instructions"]})
    candidates.sort(key=lambda x: -x["score"])
    return {"candidates": candidates, "excluded": excluded}
