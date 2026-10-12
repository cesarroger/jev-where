#!/usr/bin/env python3
"""Generate assets/src/how-it-works.excalidraw, the hand-drawn "How it works" diagram.

Open the .excalidraw file at https://excalidraw.com to edit it by hand.
Render it to assets/how-it-works.svg with assets/src/render_diagram.html (see README).
Colors match the banner (assets/src/make_banner.py).
"""
import json
import pathlib
import random

INK = "#1E1B3A"
SOFT = "#4A4566"
SKY, SUN, MINT, LILAC, PINK, LIME = "#9FD8FF", "#FFD966", "#8EEBD2", "#CDBDFF", "#FFC1E0", "#B8F03A"
TOMATO = "#FF6B57"
FONT = 5  # Excalifont, Excalidraw's hand-drawn font

rng = random.Random(11)
els = []


def base(kind, x, y, w, h, *, stroke=INK, bg="transparent", fill="solid", sw=2, style="solid",
         rough=2, angle=0.0, groups=None, roundness=None, **extra):
    e = {
        "id": f"{kind}-{len(els)}", "type": kind, "x": x, "y": y, "width": w, "height": h,
        "angle": angle, "strokeColor": stroke, "backgroundColor": bg, "fillStyle": fill,
        "strokeWidth": sw, "strokeStyle": style, "roughness": rough, "opacity": 100,
        "groupIds": groups or [], "frameId": None, "roundness": roundness,
        "seed": rng.randint(1, 2**31 - 1), "version": 1, "versionNonce": rng.randint(1, 2**31 - 1),
        "isDeleted": False, "boundElements": None, "updated": 1, "link": None, "locked": False,
    }
    e.update(extra)
    els.append(e)
    return e


def text(x, y, w, s, size=24, color=INK, align="center", angle=0.0, groups=None):
    lines = s.count("\n") + 1
    return base("text", x, y, w, lines * size * 1.25, stroke=color, angle=angle, groups=groups,
                text=s, originalText=s, fontSize=size, fontFamily=FONT, textAlign=align,
                verticalAlign="top", containerId=None, autoResize=False, lineHeight=1.25)


def path(kind, x, y, pts, **kw):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    extra = {"points": pts, "lastCommittedPoint": None, "startBinding": None, "endBinding": None,
             "startArrowhead": None, "endArrowhead": "arrow" if kind == "arrow" else None}
    if kind == "arrow":
        extra["elbowed"] = False
    extra.update(kw.pop("extra", {}))
    return base(kind, x, y, max(xs) - min(xs), max(ys) - min(ys), roundness={"type": 2}, **kw, **extra)


def card(x, y, color, num, title, sub, angle, style="solid", w=360, h=180):
    g = [f"card-{num}"]
    base("rectangle", x, y, w, h, bg=color, sw=3, style=style, angle=angle, groups=g, roundness={"type": 3})
    text(x + 18, y + 30, w - 36, title, size=30, groups=g)
    if sub:
        title_h = (title.count("\n") + 1) * 30 * 1.25
        text(x + 18, y + 30 + title_h + 10, w - 36, sub, size=20, color=SOFT, groups=g)
    base("ellipse", x - 20, y - 22, 48, 48, bg=LIME if num != 6 else SUN, sw=3, groups=g)
    text(x - 20, y - 22 + 8, 48, str(num), size=26, groups=g)


# --- the six steps (snake layout) ---------------------------------------------
card(40, 60, SKY, 1, "Your app", "code, or a short\ndescription", -0.015)
card(520, 60, SUN, 2, "Find fuzzy decisions", "regex rules · yes/no LLM calls\nrouting · gates · ranking", 0.012)
card(1000, 60, MINT, 3, "Write the typed\nquestion", "", -0.01)
card(1000, 420, LILAC, 4, "Fetch live\nprecedents", "awesome-jev category files,\nfresh on every run", 0.014)
card(520, 420, PINK, 5, "Ranked report", "value · effort · risk\n+ the best first experiment", -0.012)
card(40, 420, LIME, 6, "Starter code", "from the current TypeSafe docs\n+ a tiny test harness", 0.01, style="dashed")

# Choice / Score / Noul chips inside card 3
for i, (label, color) in enumerate((("Choice", TOMATO), ("Score", "#4CB7FF"), ("Noul", "#A78BFA"))):
    cx = 1022 + i * 108
    base("rectangle", cx, 172, 98, 42, bg=color, sw=2, roundness={"type": 3}, angle=rng.uniform(-0.05, 0.05),
         groups=["chips"])
    text(cx, 180, 98, label, size=21, groups=["chips"])

# --- arrows -------------------------------------------------------------------
path("arrow", 408, 150, [[0, 0], [52, -16], [104, 0]], sw=3)
path("arrow", 888, 150, [[0, 0], [52, 14], [104, 0]], sw=3)
path("arrow", 1368, 120, [[0, 0], [62, 150], [6, 360]], sw=3)
path("arrow", 992, 510, [[0, 0], [-52, 16], [-104, 0]], sw=3)
path("arrow", 512, 510, [[0, 0], [-52, -16], [-104, 0]], sw=3, style="dashed", stroke=TOMATO)
text(404, 548, 120, "only if you\nsay yes", size=18, color=TOMATO, angle=-0.04)

# --- side notes ---------------------------------------------------------------
text(46, 252, 330, "it reads your code.\nit never edits it.", size=20, color=TOMATO, angle=-0.03)
text(1020, 610, 340, "no network? it says so,\nand cites nothing", size=18, color=SOFT, angle=0.02)

# --- Jev, between the rows ----------------------------------------------------
J = ["jev"]
jx, jy = 600, 300
path("line", jx + 18, jy + 70, [[0, 0], [-2, 18]], sw=4, groups=J)
path("line", jx + 46, jy + 70, [[0, 0], [2, 18]], sw=4, groups=J)
path("line", jx + 32, jy - 2, [[0, 0], [2, -18]], sw=3, groups=J)
base("ellipse", jx + 24, jy - 34, 20, 20, bg=SUN, sw=2, groups=J)
base("rectangle", jx, jy, 64, 72, bg=LIME, sw=3, groups=J, roundness={"type": 3})
for ex in (jx + 10, jx + 34):
    base("ellipse", ex, jy + 14, 20, 20, bg="#FFFFFF", sw=2, rough=1, groups=J)
    base("ellipse", ex + 6, jy + 21, 9, 9, bg=INK, sw=1, rough=0, groups=J)
path("line", jx + 22, jy + 48, [[0, 0], [10, 7], [20, 0]], sw=2.5, groups=J)
path("line", jx + 64, jy + 36, [[0, 0], [22, -16]], sw=3, groups=J)
base("ellipse", jx + 80, jy - 2, 34, 34, bg="#4CB7FF", fill="hachure", sw=3, groups=J)

# speech bubble
base("rectangle", jx + 162, jy + 4, 236, 62, bg="#FFFFFF", sw=2, roundness={"type": 3}, groups=["bubble"])
path("line", jx + 162, jy + 22, [[0, 0], [-34, 8], [0, 20]], sw=2, groups=["bubble"])
text(jx + 162, jy + 17, 236, "so... JEV WHERE?", size=26, groups=["bubble"])

scene = {
    "type": "excalidraw",
    "version": 2,
    "source": "https://github.com/cesarroger/jev-where",
    "elements": els,
    "appState": {"viewBackgroundColor": "#FFF4DE", "gridSize": None},
    "files": {},
}

if __name__ == "__main__":
    out = pathlib.Path(__file__).resolve().parent / "how-it-works.excalidraw"
    out.write_text(json.dumps(scene, indent=1))
    print(f"wrote {out} ({len(els)} elements)")
