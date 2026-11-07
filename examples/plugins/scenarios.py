def scenario_created(h):
    return h.unit.dispatch({"type": "created", "id": 1})


def scenario_unknown(h):
    return h.unit.dispatch({"type": "moved", "id": 2})
