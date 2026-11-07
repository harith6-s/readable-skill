"""Repair actions: retry a failed refund, unlock an order."""

from shop import audit, orders_store
from shop.checkout_v2.shared import CANCELLED, PAID, REFUND_FAILED, money, refund_payment


def retry_refund(order_id):
    order = orders_store.load_order(order_id)
    if order["status"] != REFUND_FAILED:
        return {"ok": False, "reason": "nothing to retry"}
    if not refund_payment(order):
        orders_store.mark(order["id"], REFUND_FAILED)
        return {"ok": False, "reason": "refund"}
    orders_store.mark(order["id"], CANCELLED)
    audit.log("order_cancelled", order_id=order["id"], refunded=money(order["totals"]["total"]))
    return {"ok": True}


def unlock_order(order_id):
    orders_store.mark(order_id, PAID)
    audit.log("order_unlocked", order_id=order_id)
    return {"ok": True}
