from db.database import q
from integrations.delhivery import get_client


def check_serviceability(hid, pincode):
    return get_client().check_serviceability(hid, pincode)


def create_shipment(hid, order_id, pincode, key):
    res = get_client().create_shipment(hid, pincode, key, reference=f"order-{order_id}")
    q("UPDATE orders SET external_delivery_id=%s, delivery_status='CREATED', updated_at=now() WHERE id=%s",
      (res["external_id"], order_id))
    return res


def check_delivery(hid, order_id, external_id):
    res = get_client().track_shipment(hid, external_id)
    if res["status"] in ("DELIVERED", "DELAYED"):
        q("UPDATE orders SET delivery_status=%s, updated_at=now() WHERE id=%s", (res["status"], order_id))
    return res
