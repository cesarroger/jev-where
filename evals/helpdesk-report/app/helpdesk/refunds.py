"""Auto-approve small refunds."""

AUTO_REFUND_LIMIT_USD = 50


def auto_refund(ticket: dict, order: dict) -> bool:
    body = ticket["body"].lower()
    asked = "refund" in body or "money back" in body
    duplicate = "charged twice" in body or "double charge" in body
    return asked and duplicate and order["amount_usd"] <= AUTO_REFUND_LIMIT_USD
