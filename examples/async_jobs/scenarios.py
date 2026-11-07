def scenario_fetch_all(h):
    h.stub("feeds.client.get").returns({"items": [{"id": 2}, {"id": 1}]})
    return h.unit.fetch_all(["a", "b"])
