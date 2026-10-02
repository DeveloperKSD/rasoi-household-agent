from db.database import q, one


def apply_inventory_changes(hid, shopping_items, meal_ingredients, substitutions, conn=None):
    """Add purchased items, then deduct what the meal consumed (substitutes deducted instead of originals)."""
    for it in shopping_items:
        q("""INSERT INTO inventory (household_id,ingredient,quantity,unit) VALUES (%s,%s,%s,%s)
             ON CONFLICT (household_id, ingredient)
             DO UPDATE SET quantity = inventory.quantity + EXCLUDED.quantity, updated_at=now()""",
          (hid, it["name"], it["quantity"], it["unit"]), conn=conn)
    swap = {s["from"]: s["to"] for s in substitutions}
    for i in meal_ingredients:
        used = swap.get(i["name"], i["name"])
        q("""UPDATE inventory SET quantity = GREATEST(quantity - %s, 0), updated_at=now()
             WHERE household_id=%s AND ingredient=%s""", (i["quantity"], hid, used), conn=conn)


def record_meal(hid, meal_id, plan_date):
    if one("SELECT 1 AS x FROM meal_history WHERE household_id=%s AND meal_id=%s AND date=%s", (hid, meal_id, plan_date)):
        return
    q("INSERT INTO meal_history (household_id,meal_id,date,status) VALUES (%s,%s,%s,'planned')", (hid, meal_id, plan_date))


def record_meal_feedback(hid, meal_id, plan_date, rating, feedback=None):
    q("UPDATE meal_history SET rating=%s, feedback=%s WHERE household_id=%s AND meal_id=%s AND date=%s",
      (rating, feedback, hid, meal_id, plan_date))
