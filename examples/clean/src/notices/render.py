"""Render a notice title and body for one language."""

TITLES = {"en": "Payment received", "th": "ได้รับชำระเงินแล้ว"}


def render_many(language, rows):
    return [render_notice(language, row["name"], row["amount"]) for row in rows]


def render_notice(language, name, amount):
    title = TITLES.get(language, TITLES["en"])
    if language == "th":
        body = f"คุณ {name} ชำระเงิน {amount:,.2f} บาท"
    else:
        body = f"{name} paid {amount:,.2f}"
    return {"title": title, "body": body}
