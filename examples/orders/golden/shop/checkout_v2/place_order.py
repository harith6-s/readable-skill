"""Step 2: reserve stock, charge, save the order and send the receipt (and the entry point that queues it)."""

from shop import audit, inventory, mailer, orders_store, queue
from shop.checkout_v2.constants import PAID
from shop.checkout_v2.shared import cart_totals, money, release_all
from shop.config import GATEWAY_URL, RECEIPT_SENDER
from shop.payments import Gateway, GatewayError


def queue_place_order(cart, customer):
    queue.enqueue("place_order", cart, customer)
    return {"queued": True}


def place_order(cart, customer, notify=True):
    totals = cart_totals(cart)
    reserved = _reserve_all(cart)
    if not reserved["ok"]:
        audit.log("order_rejected", customer=customer["id"], short=reserved["short"])
        return {"ok": False, "short": reserved["short"]}
    capture = True    # nothing passes capture=False, the authorize-only branch stays
    try:
        gateway = Gateway(GATEWAY_URL)
        if not capture:
            paid = gateway.authorize(totals["total"], customer["token"])
        else:
            paid = gateway.charge(totals["total"], customer["token"])
    except GatewayError as error:
        release_all(cart)
        audit.log("charge_failed", customer=customer["id"], reason=str(error))
        return {"ok": False, "reason": "payment"}
    lines = []
    for item in cart["items"]:
        lines.append({"sku": item["sku"], "qty": item["qty"], "amount": item["price"] * item["qty"]})
    record = {"customer": customer["id"], "lines": lines, "totals": totals,
              "payment": paid["id"], "status": PAID}
    order_id = orders_store.save_order(record)
    if notify:
        cc = ()    # nothing passes cc, the copy branch stays
        body = "\n".join(f"{line['sku']} x{line['qty']}  {money(line['amount'])}" for line in lines)
        body += f"\nTotal {money(totals['total'])}"
        if cc:
            body += "\nCopied to " + ", ".join(cc)
        mailer.send(customer["email"], f"Receipt {order_id}", body, sender=RECEIPT_SENDER, cc=cc)
    audit.log("order_placed", order_id=order_id)
    return {"ok": True, "order_id": order_id}


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
