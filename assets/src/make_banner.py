#!/usr/bin/env python3
"""Generate assets/banner.svg: a seek-and-find crowd of code critters with Jev hidden in it.

Run from anywhere:  python3 assets/src/make_banner.py
Change SEED to reshuffle the crowd. Change JEV_AT to move Jev.
"""
import math
import pathlib
import random

W, H = 1280, 560
SEED = 7
JEV_AT = (1046, 478)
HINT_AT = (994, 474)  # the regex blob Jev hangs out with

INK = "#1E1B3A"
BG = "#FFF4DE"
PALETTE = ["#FF6B57", "#FFC93C", "#3DD9B3", "#4CB7FF", "#A78BFA", "#FF8FC7", "#FF9F43"]
LIME = "#B8F03A"  # reserved for Jev and the title's "?"
FONT = "ui-rounded, 'SF Pro Rounded', 'Arial Rounded MT Bold', Nunito, 'Trebuchet MS', system-ui, sans-serif"
MONO = "ui-monospace, 'SF Mono', SFMono-Regular, Menlo, Consolas, monospace"
WORDS = ["YES?", "NO?", "maybe", "spam?", "urgent?", "route?", "refund?", "angry?", "rank?", "allow?"]

rng = random.Random(SEED)


def eyes(cx, cy, r, look, gap):
    lx, ly = look
    s = ""
    for dx in (-gap, gap):
        s += f'<circle cx="{cx + dx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="#fff" stroke="{INK}" stroke-width="2"/>'
        s += f'<circle cx="{cx + dx + lx * r * 0.42:.1f}" cy="{cy + ly * r * 0.42:.1f}" r="{r * 0.5:.1f}" fill="{INK}"/>'
    return s


def regex_blob(c, look):
    return (
        f'<path d="M -22 14 C -27 -4 -16 -23 0 -23 C 16 -23 27 -4 22 14 C 18 23 -18 23 -22 14 Z" '
        f'fill="{c}" stroke="{INK}" stroke-width="3"/>'
        + eyes(0, -7, 6, look, 8)
        + f'<text x="0" y="13" text-anchor="middle" font-family="{MONO}" font-size="11" font-weight="800" fill="{INK}">/.*/</text>'
    )


def ticket(c, look):
    return (
        '<path d="M -18 -22 H 10 L 18 -14 V 22 H -18 Z" fill="#fff"/>'
        f'<rect x="-16.5" y="-20.5" width="7" height="41" fill="{c}"/>'
        f'<path d="M -18 -22 H 10 L 18 -14 V 22 H -18 Z M 10 -22 V -14 H 18" fill="none" stroke="{INK}" '
        'stroke-width="3" stroke-linejoin="round"/>'
        + eyes(3, -4, 5.5, look, 7)
        + f'<path d="M -5 10 H 12 M -5 16 H 7" stroke="{INK}" stroke-width="2.5" stroke-linecap="round"/>'
    )


def bubble(c, look):
    word = rng.choice(WORDS)
    w = 10 + 8.2 * len(word)
    h = w / 2
    return (
        f'<path d="M {-h} -16 H {h} Q {h + 8} -16 {h + 8} -8 V 6 Q {h + 8} 14 {h} 14 H -2 L -11 25 L -9 14 '
        f'H {-h} Q {-h - 8} 14 {-h - 8} 6 V -8 Q {-h - 8} -16 {-h} -16 Z" fill="{c}" stroke="{INK}" '
        'stroke-width="3" stroke-linejoin="round"/>'
        f'<text x="0" y="4" text-anchor="middle" font-family="{FONT}" font-size="14" font-weight="800" fill="{INK}">{word}</text>'
    )


def bug(c, look):
    legs = "".join(
        f'<path d="M {sx * 9} {y} L {sx * 21} {y + dy}" stroke="{INK}" stroke-width="3" stroke-linecap="round"/>'
        for sx in (-1, 1)
        for y, dy in ((-4, -7), (4, 0), (12, 7))
    )
    return (
        legs
        + f'<ellipse cx="0" cy="5" rx="14" ry="17" fill="{c}" stroke="{INK}" stroke-width="3"/>'
        + f'<path d="M 0 -11 V 21" stroke="{INK}" stroke-width="2.5"/>'
        + f'<circle cx="-6" cy="4" r="3" fill="{INK}"/><circle cx="6" cy="11" r="3" fill="{INK}"/>'
        + f'<circle cx="0" cy="-15" r="9.5" fill="{INK}"/>'
        + eyes(0, -16, 3.6, look, 4.3)
        + f'<path d="M -4 -24 Q -8 -33 -14 -32 M 4 -24 Q 8 -33 14 -32" fill="none" stroke="{INK}" '
        'stroke-width="2.5" stroke-linecap="round"/>'
    )


def braces(c, look):
    return (
        f'<text x="0" y="13" text-anchor="middle" font-family="{MONO}" font-size="46" font-weight="800" '
        f'fill="{c}" stroke="{INK}" stroke-width="3" stroke-linejoin="round" paint-order="stroke">{{ }}</text>'
        + eyes(0, -3, 5, look, 6.5)
    )


def sticky(c, look):
    return (
        f'<rect x="-20" y="-20" width="40" height="40" rx="3" fill="{c}" stroke="{INK}" stroke-width="3"/>'
        f'<path d="M -20 -12 H 20" stroke="{INK}" stroke-width="2" opacity="0.25"/>'
        + eyes(0, -3, 5.5, look, 8)
        + f'<text x="0" y="15" text-anchor="middle" font-family="{FONT}" font-size="10" font-weight="800" fill="{INK}">TODO</text>'
    )


def cog(c, look):
    teeth = "".join(
        f'<rect x="-5" y="-25" width="10" height="11" rx="2" fill="{c}" stroke="{INK}" stroke-width="3" '
        f'transform="rotate({i * 45})"/>'
        for i in range(8)
    )
    return teeth + f'<circle r="17" fill="{c}" stroke="{INK}" stroke-width="3"/>' + eyes(0, -1, 5, look, 6.5)


def if_sign(c, look):
    return (
        f'<path d="M -2 0 V 27" stroke="{INK}" stroke-width="4" stroke-linecap="round"/>'
        f'<path d="M -22 -22 H 13 L 24 -10 L 13 2 H -22 Z" fill="{c}" stroke="{INK}" stroke-width="3" stroke-linejoin="round"/>'
        f'<text x="-4" y="-4" text-anchor="middle" font-family="{MONO}" font-size="16" font-weight="800" fill="{INK}">if</text>'
    )


def duck(c, look):
    return (
        f'<path d="M -21 4 Q -23 21 0 21 Q 23 21 23 6 Q 23 -2 12 0 L 6 2 Q 0 4 -8 2 Q -17 0 -21 4 Z" '
        f'fill="#FFC93C" stroke="{INK}" stroke-width="3" stroke-linejoin="round"/>'
        f'<circle cx="8" cy="-10" r="11" fill="#FFC93C" stroke="{INK}" stroke-width="3"/>'
        f'<path d="M 17 -10 L 28 -6 L 17 -2 Z" fill="#FF9F43" stroke="{INK}" stroke-width="2.5" stroke-linejoin="round"/>'
        f'<circle cx="10" cy="-13" r="2.8" fill="{INK}"/>'
        f'<path d="M -10 9 Q -2 14 6 9" fill="none" stroke="{INK}" stroke-width="2.5" stroke-linecap="round"/>'
    )


CRITTERS = [
    (bubble, 3.0), (regex_blob, 2.0), (ticket, 2.0), (bug, 2.0),
    (braces, 1.4), (sticky, 1.4), (cog, 1.4), (if_sign, 1.4), (duck, 0.5),
]


def jev():
    return (
        f'<path d="M -8 19 V 29 M 8 19 V 29" stroke="{INK}" stroke-width="5" stroke-linecap="round"/>'
        f'<path d="M 0 -22 V -33" stroke="{INK}" stroke-width="3" stroke-linecap="round"/>'
        f'<circle cx="0" cy="-38" r="6" fill="#FFC93C" stroke="{INK}" stroke-width="2.5"/>'
        f'<rect x="-20" y="-22" width="40" height="42" rx="15" fill="{LIME}" stroke="{INK}" stroke-width="3"/>'
        + eyes(0, -8, 6.5, (0, 0.25), 8.5)
        + f'<path d="M -7 6 Q 0 12 7 6" fill="none" stroke="{INK}" stroke-width="2.5" stroke-linecap="round"/>'
        '<ellipse cx="-13" cy="3" rx="3.5" ry="2.2" fill="#FF8FC7"/>'
        '<ellipse cx="13" cy="3" rx="3.5" ry="2.2" fill="#FF8FC7"/>'
        f'<path d="M 19 2 L 30 -7" stroke="{INK}" stroke-width="3.5" stroke-linecap="round"/>'
        f'<circle cx="37" cy="-13" r="8.5" fill="#4CB7FF" fill-opacity="0.35" stroke="{INK}" stroke-width="3"/>'
        '<path d="M 33 -16 Q 35 -19 38 -19" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round"/>'
    )


# --- title -------------------------------------------------------------------
GLYPHS = {
    "J": (60, "M 60 0 V 80 A 30 30 0 0 1 0 80"),
    "E": (60, "M 60 0 H 0 V 110 H 60 M 0 55 H 46"),
    "V": (76, "M 0 0 L 38 110 L 76 0"),
    "W": (110, "M 0 0 L 24 110 L 55 34 L 86 110 L 110 0"),
    "H": (64, "M 0 0 V 110 M 64 0 V 110 M 0 55 H 64"),
    "R": (64, "M 0 110 V 0 H 34 A 27.5 27.5 0 0 1 34 55 H 0 M 30 55 L 64 110"),
    "?": (60, "M 0 30 A 30 30 0 0 1 60 30 Q 60 52 30 64 V 74"),
}
TITLE = [("J", "#FF6B57", -6, 4), ("E", "#FFC93C", 4, -3), ("V", "#3DD9B3", -3, 3), (" ", None, 0, 0),
         ("W", "#4CB7FF", 5, -2), ("H", "#A78BFA", -4, 4), ("E", "#FF8FC7", 3, -4), ("R", "#FF9F43", -5, 2),
         ("E", "#FFC93C", 4, -2), ("?", LIME, 9, -6)]
GAP, SPACE, OUTLINE, FILL = 42, 74, 40, 26


def title_svg(cx, top, scale):
    xs, x = [], 0
    for ch, *_ in TITLE:
        if ch == " ":
            x += SPACE - GAP
            xs.append(None)
            continue
        xs.append(x)
        x += GLYPHS[ch][0] + GAP
    total = x - GAP
    x0 = cx - total * scale / 2
    parts = [f'<g transform="translate({x0:.1f} {top}) scale({scale})" stroke-linecap="round" stroke-linejoin="round" fill="none">']
    for (ch, color, rot, dy), off in zip(TITLE, xs):
        if off is None:
            continue
        w, d = GLYPHS[ch]
        pivot = f"{off + w / 2} 55"
        g = f'<g transform="translate({off} {dy}) rotate({rot} {w / 2} 55)">'
        dot = ""
        if ch == "?":
            dot = (f'<circle cx="30" cy="102" r="{OUTLINE / 2}" fill="{INK}" transform="translate(6 8)"/>'
                   f'<circle cx="30" cy="102" r="{OUTLINE / 2}" fill="{INK}"/>'
                   f'<circle cx="30" cy="102" r="{FILL / 2}" fill="{color}"/>')
        g += (f'<path d="{d}" stroke="{INK}" stroke-width="{OUTLINE}" transform="translate(6 8)"/>'
              f'<path d="{d}" stroke="{INK}" stroke-width="{OUTLINE}"/>'
              f'<path d="{d}" stroke="{color}" stroke-width="{FILL}"/>'
              f'<path d="{d}" stroke="#fff" stroke-width="5" stroke-opacity="0.45" transform="translate(-4 -4)" '
              f'stroke-dasharray="0 40 26 400"/>'
              + dot + "</g>")
        parts.append(g)
    parts.append("</g>")
    return "".join(parts)


def sparkle(x, y, r, color):
    return (f'<path d="M {x} {y - r} Q {x} {y} {x + r} {y} Q {x} {y} {x} {y + r} Q {x} {y} {x - r} {y} '
            f'Q {x} {y} {x} {y - r} Z" fill="{color}" stroke="{INK}" stroke-width="2" stroke-linejoin="round"/>')


def in_clearing(x, y):
    title = ((x - 640) / 515) ** 4 + ((y - 165) / 140) ** 4 < 1
    hint_card = 20 < x < 360 and 440 < y < 545
    near_jev = math.dist((x, y), JEV_AT) < 62
    near_hint = math.dist((x, y), HINT_AT) < 50
    return title or hint_card or near_jev or near_hint


def crowd():
    items = []
    sx, sy = 63, 57
    for row, y in enumerate(range(28, H + 20, sy)):
        for col, x in enumerate(range(20 + (row % 2) * sx // 2, W + 30, sx)):
            px = x + rng.uniform(-14, 14)
            py = y + rng.uniform(-12, 12)
            if in_clearing(px, py):
                continue
            items.append((px, py))
    items.append(HINT_AT)
    out = []
    funcs, weights = zip(*CRITTERS)
    for px, py in items:
        if (px, py) == HINT_AT:
            fn, color = regex_blob, "#4CB7FF"
        else:
            fn = rng.choices(funcs, weights)[0]
            color = rng.choice(PALETTE)
        to_jev = (JEV_AT[0] - px, JEV_AT[1] - py)
        dist = math.hypot(*to_jev)
        if dist < 240:
            look = (to_jev[0] / dist, to_jev[1] / dist)
        else:
            a = rng.uniform(0, math.tau)
            look = (math.cos(a), math.sin(a))
        rot = rng.uniform(-14, 14)
        sc = rng.uniform(0.86, 1.06)
        out.append(f'<g transform="translate({px:.1f} {py:.1f}) rotate({rot:.1f}) scale({sc:.2f})">{fn(color, look)}</g>')
    return "".join(out)


def card(cx, cy, w, h, rot, fill, body):
    return (f'<g transform="translate({cx} {cy}) rotate({rot})">'
            f'<rect x="{-w / 2 + 5}" y="{-h / 2 + 6}" width="{w}" height="{h}" rx="{h / 2}" fill="{INK}"/>'
            f'<rect x="{-w / 2}" y="{-h / 2}" width="{w}" height="{h}" rx="{h / 2}" fill="{fill}" stroke="{INK}" stroke-width="3"/>'
            f'{body}</g>')


def build():
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="t d">',
        '<title id="t">JEV WHERE?</title>',
        '<desc id="d">A seek-and-find poster: a crowd of cartoon code critters (regex blobs, bugs, tickets, if-signs, '
        'speech bubbles) with Jev, a small lime mascot holding a magnifying glass, hidden among them. '
        'Tagline: a seek-and-find for the decisions hiding in your code.</desc>',
        '<defs>',
        f'<clipPath id="frame"><rect width="{W}" height="{H}" rx="30"/></clipPath>',
        '<pattern id="speckle" width="28" height="28" patternUnits="userSpaceOnUse">'
        '<path d="M 14 10 V 18 M 10 14 H 18" stroke="#F0DDB8" stroke-width="2" stroke-linecap="round"/></pattern>',
        '</defs>',
        '<g clip-path="url(#frame)">',
        f'<rect width="{W}" height="{H}" fill="{BG}"/>',
        f'<rect width="{W}" height="{H}" fill="url(#speckle)"/>',
        crowd(),
        f'<g transform="translate({JEV_AT[0]} {JEV_AT[1]}) rotate(-6) scale(0.95)">{jev()}</g>',
        sparkle(205, 92, 14, "#FFC93C"), sparkle(1088, 70, 11, "#3DD9B3"), sparkle(1110, 214, 15, "#FF8FC7"),
        sparkle(172, 226, 10, "#4CB7FF"),
        title_svg(640, 62, 0.88),
        card(640, 268, 660, 50, -1.5, "#FFFFFF",
             f'<text x="0" y="8" text-anchor="middle" font-family="{FONT}" font-size="22" font-weight="800" fill="{INK}">'
             'a seek-and-find for the decisions hiding in your code</text>'),
        card(188, 494, 300, 74, 3, "#FFC93C",
             f'<text x="0" y="-3" text-anchor="middle" font-family="{FONT}" font-size="24" font-weight="800" fill="{INK}">Can you spot Jev?</text>'
             f'<text x="0" y="21" text-anchor="middle" font-family="{FONT}" font-size="14" font-weight="700" fill="{INK}">'
             'hint: it hangs out with a regex</text>'),
        f'<rect x="2" y="2" width="{W - 4}" height="{H - 4}" rx="28" fill="none" stroke="{INK}" stroke-width="4"/>',
        '</g>',
        '</svg>',
    ]
    return "\n".join(svg) + "\n"


if __name__ == "__main__":
    out = pathlib.Path(__file__).resolve().parent.parent / "banner.svg"
    out.write_text(build())
    print(f"wrote {out} ({out.stat().st_size // 1024} KB)")
