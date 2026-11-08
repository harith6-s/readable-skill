"""Leaves called from more than one task file. None of them calls another."""

from shop import inventory
from shop.config import FREE_SHIPPING_OVER, GATEWAY_URL, SHIPPING_FEE, TAX_RATE
from shop.payments import Gateway, GatewayError


def money(value):
    return f"{value:,.2f}"


def cart_totals(cart):
    subtotal = sum(item["price"] * item["qty"] for item in cart["items"])
    shipping = 0 if subtotal >= FREE_SHIPPING_OVER else SHIPPING_FEE
    tax = round(subtotal * TAX_RATE, 2)
    return {"subtotal": subtotal, "shipping": shipping, "tax": tax, "total": subtotal + shipping + tax}


def release_all(cart):
    for item in cart["items"]:
        inventory.release(item["sku"], item["qty"])


def refund_payment(order):
    """True when the gateway took the refund, False when it refused it."""
    try:
        Gateway(GATEWAY_URL).refund(order["payment"], order["totals"]["total"])
    except GatewayError:
        return False
    return True
