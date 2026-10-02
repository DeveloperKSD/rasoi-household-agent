import os
from db.database import q, one, jsonable

STALE_HOURS = float(os.getenv("STALE_HOURS", "72"))


def get_inventory(hid, plan_date):
    rows = q("SELECT ingredient, quantity, unit, expiry_date FROM inventory WHERE household_id=%s ORDER BY ingredient", (hid,))
    age = one("SELECT EXTRACT(EPOCH FROM (now() - max(updated_at)))/3600 AS h FROM inventory WHERE household_id=%s", (hid,))
    hours = (age or {}).get("h") or 0
    items = []
    for r in rows:
        days = (r["expiry_date"] - plan_date).days if r["expiry_date"] else None
        items.append({**r, "expires_in_days": days, "expired": days is not None and days < 0})
    return jsonable({"items": items, "stale": hours > STALE_HOURS, "hours_since_update": round(hours, 1)})


def confirm_inventory(hid):
    q("UPDATE inventory SET updated_at=now() WHERE household_id=%s", (hid,))
