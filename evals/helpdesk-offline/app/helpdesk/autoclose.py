"""Close tickets where the customer only says thanks."""
import re

THANKS_ONLY = re.compile(r"^\s*(thanks?|thank you|thx|ty|cheers)[\s!.]*$", re.I)


def should_close(latest_reply: str) -> bool:
    return bool(THANKS_ONLY.match(latest_reply))
