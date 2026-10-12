"""Route inbound tickets to a team queue."""
import re

ROUTES = [
    ("billing", re.compile(r"\b(invoice|charge[ds]?|refund|billing|payment|card)\b", re.I)),
    ("technical", re.compile(r"\b(error|bug|crash|500|api|not working|broken)\b", re.I)),
    ("account", re.compile(r"\b(password|login|log in|locked|2fa|username)\b", re.I)),
    ("sales", re.compile(r"\b(pricing|quote|upgrade|enterprise|discount)\b", re.I)),
]

URGENT_WORDS = ["urgent", "asap", "immediately", "down", "outage", "can't work"]


def route(ticket: dict) -> str:
    text = f"{ticket['subject']} {ticket['body']}"
    for team, pattern in ROUTES:
        if pattern.search(text):
            return team
    return "general"


def priority(ticket: dict) -> int:
    """0 = low, 1 = normal, 2 = high."""
    text = ticket["body"].lower()
    hits = sum(word in text for word in URGENT_WORDS)
    if hits >= 2 or "!!!" in text:
        return 2
    if hits == 1:
        return 1
    return 0
