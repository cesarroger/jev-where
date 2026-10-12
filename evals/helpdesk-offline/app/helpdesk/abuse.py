"""Hold abusive tickets before an agent sees them."""
import re

BANNED = re.compile(r"\b(idiot|stupid|moron|scam(mers)?|f\*+k)\b", re.I)


def should_hold(body: str) -> bool:
    return bool(BANNED.search(body))
