"""Step 1: price a cart and report what is short."""

from shop import inventory
from shop.checkout_v2.shared import money
from shop.config import FREE_SHIPPING_OVER, SHIPPING_FEE, TAX_RATE


def preview_order(cart):
    subtotal = sum(item["price"] * item["qty"] for item in cart["items"])
    shipping = 0 if subtotal >= FREE_SHIPPING_OVER else SHIPPING_FEE
    tax = round(subtotal * TAX_RATE, 2)
    totals = {"subtotal": subtotal, "shipping": shipping, "tax": tax, "total": subtotal + shipping + tax}
    problems = []
    for item in cart["items"]:
        if inventory.available(item["sku"]) < item["qty"]:
            problems.append({"sku": item["sku"], "short": item["qty"] - inventory.available(item["sku"])})
    return {"total": money(totals["total"]), "totals": totals, "problems": problems, "ok": not problems}
