def scenario_bank_statement(h):
    h.stub("ledger_app.storage.read_lines").returns(["2026-01-02,100.5,salary", "2026-01-03,0,void", "2026-01-04,-20,fee"])
    return h.unit.import_bank_statement("bank.csv")


def scenario_card_statement(h):
    h.stub("ledger_app.storage.read_lines").returns(["2026-02-01,30,coffee", "2026-02-02,12.5,books"])
    return h.unit.import_card_statement("card.csv")


def scenario_empty_statement(h):
    h.stub("ledger_app.storage.read_lines").returns([])
    return h.unit.import_bank_statement("empty.csv")
