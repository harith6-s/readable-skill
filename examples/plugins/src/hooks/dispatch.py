"""Send an event to the handler named after its type."""

from hooks import handlers


def dispatch(event):
    handler = getattr(handlers, "on_" + event["type"], None)
    if handler is None:
        return {"handled": None}
    return handler(event)
