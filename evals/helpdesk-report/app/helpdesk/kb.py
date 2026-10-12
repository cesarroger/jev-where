"""Suggest help-center articles to the agent."""


def suggest_articles(body: str, articles: list[dict], k: int = 3) -> list[dict]:
    words = set(body.lower().split())

    def overlap(article: dict) -> int:
        return len(words & set(article["title"].lower().split()))

    return sorted(articles, key=overlap, reverse=True)[:k]
