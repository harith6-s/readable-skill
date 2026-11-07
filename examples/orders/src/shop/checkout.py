"""Checkout: price a cart, place an order, cancel and refund it."""

from shop import audit, inventory, mailer, orders_store, queue
from shop.config import FREE_SHIPPING_OVER, GATEWAY_URL, RECEIPT_SENDER, SHIPPING_FEE, TAX_RATE
from shop.payments import Gateway, GatewayError


def _money(value):
    return f"{value:,.2f}"


def _subtotal(cart):
    return sum(item["price"] * item["qty"] for item in cart["items"])


def _shipping(subtotal):
    if subtotal >= FREE_SHIPPING_OVER:
        return 0
    return SHIPPING_FEE


def _totals(cart):
    subtotal = _subtotal(cart)
    shipping = _shipping(subtotal)
    tax = round(subtotal * TAX_RATE, 2)
    return {"subtotal": subtotal, "shipping": shipping, "tax": tax, "total": subtotal + shipping + tax}


def _gateway():
    return Gateway(GATEWAY_URL)


def _release_all(cart):
    for item in cart["items"]:
        inventory.release(item["sku"], item["qty"])


def _reserve_all(cart):
    taken = []
    for item in cart["items"]:
        if inventory.available(item["sku"]) < item["qty"]:
            for earlier in taken:
                inventory.release(earlier["sku"], earlier["qty"])
            return {"ok": False, "short": item["sku"]}
        inventory.reserve(item["sku"], item["qty"])
        taken.append(item)
    return {"ok": True, "short": None}


def _charge(customer, amount, capture=True):
    gateway = _gateway()
    if not capture:
        return gateway.authorize(amount, customer["token"])
    return gateway.charge(amount, customer["token"])


def _order_lines(cart):
    lines = []
    for item in cart["items"]:
        lines.append({"sku": item["sku"], "qty": item["qty"], "amount": item["price"] * item["qty"]})
    return lines


def _receipt_lines(cart):
    lines = []
    for item in cart["items"]:
        lines.append({"sku": item["sku"], "qty": item["qty"], "amount": item["price"] * item["qty"]})
    return lines


def _send_receipt(customer, order_id, lines, totals, cc=()):
    body = "\n".join(f"{line['sku']} x{line['qty']}  {_money(line['amount'])}" for line in lines)
    body += f"\nTotal {_money(totals['total'])}"
    if cc:
        body += "\nCopied to " + ", ".join(cc)
    mailer.send(customer["email"], f"Receipt {order_id}", body, sender=RECEIPT_SENDER, cc=cc)


def _refund(order):
    try:
        _gateway().refund(order["payment"], order["totals"]["total"])
    except GatewayError:
        orders_store.mark(order["id"], "refund_failed")
        return {"ok": False, "reason": "refund"}
    orders_store.mark(order["id"], "cancelled")
    audit.log("order_cancelled", order_id=order["id"], refunded=_money(order["totals"]["total"]))
    return {"ok": True}


def preview_order(cart):
    totals = _totals(cart)
    problems = []
    for item in cart["items"]:
        if inventory.available(item["sku"]) < item["qty"]:
            problems.append({"sku": item["sku"], "short": item["qty"] - inventory.available(item["sku"])})
    return {"total": _money(totals["total"]), "totals": totals, "problems": problems, "ok": not problems}


def queue_place_order(cart, customer):
    queue.enqueue("place_order", cart, customer)
    return {"queued": True}


def place_order(cart, customer, notify=True):
    totals = _totals(cart)
    reserved = _reserve_all(cart)
    if not reserved["ok"]:
        audit.log("order_rejected", customer=customer["id"], short=reserved["short"])
        return {"ok": False, "short": reserved["short"]}
    try:
        paid = _charge(customer, totals["total"])
    except GatewayError as error:
        _release_all(cart)
        audit.log("charge_failed", customer=customer["id"], reason=str(error))
        return {"ok": False, "reason": "payment"}
    record = {"customer": customer["id"], "lines": _order_lines(cart), "totals": totals,
              "payment": paid["id"], "status": "paid"}
    order_id = orders_store.save_order(record)
    if notify:
        _send_receipt(customer, order_id, _receipt_lines(cart), totals)
    audit.log("order_placed", order_id=order_id)
    return {"ok": True, "order_id": order_id}


def cancel_order(order_id):
    order = orders_store.load_order(order_id)
    if order["status"] != "paid":
        return {"ok": False, "reason": "not paid"}
    orders_store.mark(order_id, "cancelling")
    _release_all({"items": order["lines"]})
    return _refund(order)


def retry_refund(order_id):
    order = orders_store.load_order(order_id)
    if order["status"] != "refund_failed":
        return {"ok": False, "reason": "nothing to retry"}
    return _refund(order)


def unlock_order(order_id):
    orders_store.mark(order_id, "paid")
    audit.log("order_unlocked", order_id=order_id)
    return {"ok": True}
