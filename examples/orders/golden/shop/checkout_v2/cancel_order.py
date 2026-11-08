"""Step 3: cancel a paid order and refund it."""

from shop import audit, orders_store
from shop.checkout_v2.constants import CANCELLED, CANCELLING, PAID, REFUND_FAILED
from shop.checkout_v2.shared import money, refund_payment, release_all


def cancel_order(order_id):
    order = orders_store.load_order(order_id)
    if order["status"] != PAID:
        return {"ok": False, "reason": "not paid"}
    orders_store.mark(order_id, CANCELLING)
    release_all({"items": order["lines"]})
    if not refund_payment(order):
        orders_store.mark(order["id"], REFUND_FAILED)
        return {"ok": False, "reason": "refund"}
    orders_store.mark(order["id"], CANCELLED)
    audit.log("order_cancelled", order_id=order["id"], refunded=money(order["totals"]["total"]))
    return {"ok": True}
