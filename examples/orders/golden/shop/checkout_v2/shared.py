"""Leaves called from more than one task file. None of them calls another."""

from shop import audit, inventory, orders_store
from shop.config import GATEWAY_URL
from shop.payments import Gateway, GatewayError


def money(value):
    return f"{value:,.2f}"


def release_all(cart):
    for item in cart["items"]:
        inventory.release(item["sku"], item["qty"])


def refund(order):
    try:
        Gateway(GATEWAY_URL).refund(order["payment"], order["totals"]["total"])
    except GatewayError:
        orders_store.mark(order["id"], "refund_failed")
        return {"ok": False, "reason": "refund"}
    orders_store.mark(order["id"], "cancelled")
    audit.log("order_cancelled", order_id=order["id"], refunded=f"{order['totals']['total']:,.2f}")
    return {"ok": True}
