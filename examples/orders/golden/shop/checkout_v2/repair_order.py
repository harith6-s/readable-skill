"""Repair actions: retry a failed refund, unlock an order."""

from shop import audit, orders_store
from shop.checkout_v2.shared import refund


def retry_refund(order_id):
    order = orders_store.load_order(order_id)
    if order["status"] != "refund_failed":
        return {"ok": False, "reason": "nothing to retry"}
    return refund(order)


def unlock_order(order_id):
    orders_store.mark(order_id, "paid")
    audit.log("order_unlocked", order_id=order_id)
    return {"ok": True}
