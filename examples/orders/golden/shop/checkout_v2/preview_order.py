"""Step 1: price a cart and report what is short."""

from shop import inventory
from shop.checkout_v2.shared import cart_totals, money


def preview_order(cart):
    totals = cart_totals(cart)
    problems = []
    for item in cart["items"]:
        if inventory.available(item["sku"]) < item["qty"]:
            problems.append({"sku": item["sku"], "short": item["qty"] - inventory.available(item["sku"])})
    return {"total": money(totals["total"]), "totals": totals, "problems": problems, "ok": not problems}
