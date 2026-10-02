from datetime import date
from db.database import q, one, J, jsonable

RELAXABLE = {"exclude_contains", "exclude_ingredient", "min_protein", "max_meal_cost"}


def build_constraints(members, rules, plan_date: date):
    c = {"diet": None, "exclude_contains": [], "exclude_ingredients": [], "min_protein": None,
         "max_meal_cost": None, "substitutions": {}}
    labels, active = [], []

    def label(text, rule=None):
        if text not in labels:
            labels.append(text)
        if rule is not None:
            active.append({"id": rule["id"], "label": text,
                           "relaxable": rule["source"] != "setup" and rule["rule_type"] in RELAXABLE})

    for m in members:
        if m["diet"] == "vegetarian":
            c["diet"] = "vegetarian"
        for r in m["restrictions"] or []:
            if r.startswith("no_") and r[3:] not in c["exclude_contains"]:
                c["exclude_contains"].append(r[3:]); label(f"no {r[3:]}")
    for r in rules:
        v, t = r["rule_value"], r["rule_type"]
        if t in ("diet", "religious_restriction") and v.get("value") in ("vegetarian", "no_non_veg"):
            c["diet"] = "vegetarian"
        elif t == "exclude_contains":
            if v["value"] not in c["exclude_contains"]:
                c["exclude_contains"].append(v["value"])
            label(f"no {v['value']}", r)
        elif t == "exclude_ingredient":
            until = v.get("until")
            if until and date.fromisoformat(until) < plan_date:
                continue  # expired temporary rule
            c["exclude_ingredients"].append(v["ingredient"])
            label(f"no {v['ingredient']}" + (f" (until {until})" if until else ""), r)
        elif t == "min_protein":
            c["min_protein"] = v["value"]; label(f"at least {v['value']}g protein", r)
        elif t == "max_meal_cost":
            c["max_meal_cost"] = v["value"]; label(f"meal under ₹{v['value']}", r)
        elif t == "approved_substitution":
            c["substitutions"][v["from"]] = v["to"]
    if c["diet"]:
        labels.insert(0, "vegetarian")
    return {"constraints": c, "labels": labels, "active_rules": active}


def get_household_context(hid, plan_date: date):
    h = one("SELECT * FROM households WHERE id=%s", (hid,))
    members = q("SELECT * FROM members WHERE household_id=%s ORDER BY id", (hid,))
    rules = q("SELECT * FROM household_rules WHERE household_id=%s ORDER BY priority DESC, id", (hid,))
    recent = q("""SELECT m.name, mh.date FROM meal_history mh JOIN meals m ON m.id=mh.meal_id
                  WHERE mh.household_id=%s ORDER BY mh.date DESC LIMIT 5""", (hid,))
    built = build_constraints(members, rules, plan_date)
    prefs = sorted({p for m in members for p in (m["preferences"] or [])})
    return jsonable({
        "id": hid, "name": h["name"], "budget": h["budget_daily"], "currency": h["currency"],
        "pincode": h["pincode"], "nutrition_goal": h["nutrition_goal"],
        "member_count": len(members), "members": [m["name"] for m in members],
        "diet": built["constraints"]["diet"], "preferences": prefs, "recent_meals": recent,
        "constraints": built["constraints"], "constraint_labels": built["labels"],
        "active_rules": built["active_rules"],
    })


def add_voice_rule(hid, interp):
    """Persist a rule derived from a voice note (relaxable by a human later)."""
    if interp.get("intent") != "exclude_ingredient" or not interp.get("ingredient"):
        return None
    row = one("""INSERT INTO household_rules (household_id,rule_type,rule_value,source)
                 VALUES (%s,'exclude_ingredient',%s,'voice') RETURNING id""",
              (hid, J({"ingredient": interp["ingredient"], "until": interp.get("date")})))
    return row["id"]
