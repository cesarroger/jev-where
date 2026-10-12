"""Flag angry customers so a senior agent picks the ticket up."""
from openai import OpenAI

client = OpenAI()


def is_angry(body: str) -> bool:
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Answer only YES or NO."},
            {"role": "user", "content": f"Is this customer angry?\n\n{body}"},
        ],
    )
    return resp.choices[0].message.content.strip().upper().startswith("YES")
