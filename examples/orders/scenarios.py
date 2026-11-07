"""Parity scenarios for shop.checkout: every entry point, on its success path and on each failure it handles.

The three flags nobody passes (place_order(notify=), _charge(capture=), _send_receipt(cc=)) cannot be reached from
any entry point, so no scenario reaches their other branch: `parity.py coverage` lists those call sites on purpose.
"""

CART = {"items": [{"sku": "A-1", "price": 400, "qty": 2}, {"sku": "B-2", "price": 150, "qty": 1}]}
BIG_CART = {"items": [{"sku": "C-3", "price": 1200, "qty": 1}]}
CUSTOMER = {"id": 11, "email": "buyer@example.test", "token": "tok_11"}
PAID_ORDER = {"id": 5, "status": "paid", "payment": "pay_5", "totals": {"total": 1070.5},
              "lines": [{"sku": "A-1", "qty": 2, "amount": 800}]}


def scenario_preview_all_in_stock(h):
    h.stub("shop.inventory.available").returns(50)
    return h.unit.preview_order(CART)


def scenario_preview_free_shipping(h):
    h.stub("shop.inventory.available").returns(50)
    return h.unit.preview_order(BIG_CART)


def scenario_preview_short_stock(h):
    h.stub("shop.inventory.available").answers(lambda sku: 1 if sku == "A-1" else 50)
    return h.unit.preview_order(CART)


def scenario_queue_place_order(h):
    return h.unit.queue_place_order(CART, CUSTOMER)


def scenario_place_order_success(h):
    h.stub("shop.inventory.available").returns(50)
    h.stub("shop.payments.Gateway().charge").returns({"id": "pay_9"})
    h.stub("shop.orders_store.save_order").returns(9)
    return h.unit.place_order(CART, CUSTOMER)


def scenario_place_order_out_of_stock(h):
    h.stub("shop.inventory.available").answers(lambda sku: 1 if sku == "B-2" else 50)
    return h.unit.place_order(CART, CUSTOMER)


def scenario_place_order_declined(h):
    h.stub("shop.inventory.available").returns(50)
    h.stub("shop.payments.Gateway().charge").raises(h.error("shop.payments.GatewayError", "declined"))
    return h.unit.place_order(CART, CUSTOMER)


def scenario_cancel_order_success(h):
    h.stub("shop.orders_store.load_order").returns(dict(PAID_ORDER))
    return h.unit.cancel_order(5)


def scenario_cancel_order_not_paid(h):
    h.stub("shop.orders_store.load_order").returns(dict(PAID_ORDER, status="cancelled"))
    return h.unit.cancel_order(5)


def scenario_cancel_order_refund_fails(h):
    h.stub("shop.orders_store.load_order").returns(dict(PAID_ORDER))
    h.stub("shop.payments.Gateway().refund").raises(h.error("shop.payments.GatewayError", "no funds"))
    return h.unit.cancel_order(5)


def scenario_retry_refund_success(h):
    h.stub("shop.orders_store.load_order").returns(dict(PAID_ORDER, status="refund_failed"))
    return h.unit.retry_refund(5)


def scenario_retry_refund_nothing_to_retry(h):
    h.stub("shop.orders_store.load_order").returns(dict(PAID_ORDER))
    return h.unit.retry_refund(5)


def scenario_unlock_order(h):
    return h.unit.unlock_order(5)
