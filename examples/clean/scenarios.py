def scenario_render_en(h):
    return h.unit.render_notice("en", "Ann", 1234.5)


def scenario_render_th(h):
    return h.unit.render_notice("th", "สมชาย", 99)


def scenario_render_many(h):
    return h.unit.render_many("en", [{"name": "A", "amount": 1}, {"name": "B", "amount": 2}])
