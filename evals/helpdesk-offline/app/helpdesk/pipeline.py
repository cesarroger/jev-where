"""Inbound email -> ticket pipeline."""
from . import abuse, autoclose, kb, refunds, router, sentiment


def handle_new_ticket(ticket: dict, order: dict | None, articles: list[dict]) -> dict:
    if abuse.should_hold(ticket["body"]):
        return {"status": "held_for_review"}
    if order and refunds.auto_refund(ticket, order):
        return {"status": "refunded"}
    return {
        "status": "open",
        "queue": router.route(ticket),
        "priority": router.priority(ticket),
        "senior": sentiment.is_angry(ticket["body"]),
        "suggested_articles": kb.suggest_articles(ticket["body"], articles),
    }


def handle_reply(ticket: dict, reply: str) -> dict:
    if autoclose.should_close(reply):
        return {"status": "closed"}
    return {"status": "open"}
