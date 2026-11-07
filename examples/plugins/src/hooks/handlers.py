from hooks import audit


def on_created(event):
    audit.log("created", id=event["id"])
    return {"handled": "created"}


def on_deleted(event):
    audit.log("deleted", id=event["id"])
    return {"handled": "deleted"}
