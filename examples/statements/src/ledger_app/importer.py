"""Import a bank or card statement file into the ledger."""

from ledger_app import ledger, storage


class StatementImporter:
    account = "cash"

    def __init__(self, source):
        self.source = source
        self.rows = []
        self.errors = []

    def run(self, path):
        self.load(path)
        self.validate()
        self.post()
        return {"posted": len(self.rows), "errors": self.errors}

    def load(self, path):
        self.rows = [self.parse_row(line) for line in storage.read_lines(path)]

    def parse_row(self, line):
        date, amount, memo = line.split(",")
        return {"date": date, "amount": float(amount), "memo": memo}

    def validate(self):
        good = []
        for row in self.rows:
            if row["amount"] == 0:
                self.errors.append(f"zero amount on {row['date']}")
            else:
                good.append(row)
        self.rows = good

    def post(self):
        for row in self.rows:
            ledger.post(self.account, row["amount"], row["memo"])


class CardImporter(StatementImporter):
    account = "card"

    def parse_row(self, line):
        row = super().parse_row(line)
        row["amount"] = -row["amount"]
        return row


def import_bank_statement(path):
    return StatementImporter("bank").run(path)


def import_card_statement(path):
    return CardImporter("card").run(path)
