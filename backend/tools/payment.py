from db.database import q, one, J
from integrations.pine_labs import get_client


def create_order_row(run_id, hid, items, amount):
    row = one("""INSERT INTO orders (run_id,household_id,items,amount,status,payment_status)
                 VALUES (%s,%s,%s,%s,'CREATED','NOT_STARTED') RETURNING id""", (run_id, hid, J(items), amount))
    return row["id"]


def create_payment(hid, order_id, amount, key):
    res = get_client().create_payment(hid, amount, "INR", key, reference=f"order-{order_id}")
    q("""UPDATE orders SET external_payment_id=%s, status='PAYMENT_PENDING', payment_status='PENDING', updated_at=now()
         WHERE id=%s""", (res["external_id"], order_id))
    return res


def check_payment(hid, order_id, external_id):
    """Only a verified PROCESSED response from the provider ever becomes SUCCESS."""
    res = get_client().get_payment(hid, external_id)
    if res["status"] == "PROCESSED":
        q("UPDATE orders SET payment_status='SUCCESS', status='PAID', updated_at=now() WHERE id=%s", (order_id,))
    elif res["status"] == "FAILED":
        q("UPDATE orders SET payment_status='FAILED', status='PAYMENT_FAILED', updated_at=now() WHERE id=%s", (order_id,))
    return res
