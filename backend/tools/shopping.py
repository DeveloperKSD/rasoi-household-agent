import math
from db.database import q


def get_catalog():
    return {r["ingredient"]: r for r in q("SELECT * FROM catalog")}


def _buy(name, qty, unit, catalog, substitute_for=None):
    qty = math.ceil(qty) if unit == "piece" else qty
    price = catalog[name]["price_per_unit"]
    return {"name": name, "quantity": qty, "unit": unit, "unit_price": price,
            "line_total": round(price * qty, 2), "substitute_for": substitute_for}


def find_substitution(name, qty, substitutions, catalog, avail):
    """Approved, like-for-like substitutes only (same quantity/unit). Pantry first, then market."""
    for s in substitutions.get(name, []):
        if avail.get(s, 0) >= qty:
            return {"to": s, "source": "pantry"}
    for s in substitutions.get(name, []):
        if s in catalog and catalog[s]["in_stock"]:
            return {"to": s, "source": "market"}
    return None


def plan_shopping(missing, substitutions, catalog, avail):
    items, subs, unresolved = [], [], []
    for m in missing:
        name, qty, unit = m["name"], m["quantity"], m["unit"]
        pantry_sub = None
        sub = find_substitution(name, qty, substitutions, catalog, avail)
        if sub and sub["source"] == "pantry":
            pantry_sub = sub
        if pantry_sub:
            subs.append({"from": name, "to": pantry_sub["to"], "source": "pantry", "quantity": qty, "unit": unit})
        elif name in catalog and catalog[name]["in_stock"]:
            items.append(_buy(name, qty, unit, catalog))
        elif sub:  # market substitute
            subs.append({"from": name, "to": sub["to"], "source": "market", "quantity": qty, "unit": unit})
            items.append(_buy(sub["to"], qty, unit, catalog, substitute_for=name))
        else:
            unresolved.append(name)
    total = round(sum(i["line_total"] for i in items), 2)
    return {"shopping_list": {"items": items, "estimated_total": total}, "substitutions": subs, "unresolved": unresolved}
