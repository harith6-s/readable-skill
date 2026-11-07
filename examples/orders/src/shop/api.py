"""The callers of checkout: what the rest of the project imports from it."""

from shop.checkout import cancel_order, place_order, preview_order, queue_place_order, retry_refund, unlock_order


def preview(cart):
    return preview_order(cart)


def submit(cart, customer):
    return queue_place_order(cart, customer)


def worker_place(cart, customer):
    return place_order(cart, customer)


def cancel(order_id):
    return cancel_order(order_id)


def support_retry(order_id):
    return retry_refund(order_id)


def support_unlock(order_id):
    return unlock_order(order_id)
