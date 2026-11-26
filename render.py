"""SVG renderers for the profile README. Light and dark variant of everything.

Fonts are Archivo, subset and embedded as base64 so the images look the same
in every browser. Text is measured with the real font metrics, so wrapping
and truncation never cut a word in half.
"""
from __future__ import annotations

import base64
from datetime import datetime, timedelta
from functools import lru_cache
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
FONTS = HERE / "fonts-src"

THEMES = {
    "light": {"field": "#FFFFFF", "ink": "#172033", "slate": "#5B6478", "rule": "#D9DEE7",
              "merged": "#0E8A6A", "merged_fill": "#0E8A6A", "review": "#B7791F", "own": "#3D5AFE",
              "fill_op": "0.14"},
    "dark": {"field": "#0D1117", "ink": "#E6EDF3", "slate": "#8B949E", "rule": "#30363D",
             "merged": "#3FB9A0", "merged_fill": "#3FB9A0", "review": "#E3B341", "own": "#8C9EFF",
             "fill_op": "0.18"},
}

FACES = {"display": "ArchivoX", "text": "ArchivoT", "strong": "ArchivoS"}
STAR = "M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.751.751 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25Z"
MERGE = "M5.45 5.154A4.25 4.25 0 0 0 9.25 7.5h1.378a2.251 2.251 0 1 1 0 1.5H9.25A5.734 5.734 0 0 1 5 7.123v3.505a2.25 2.25 0 1 1-1.5 0V5.372a2.25 2.25 0 1 1 1.95-.218ZM4.25 13.5a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Zm8.5-4.5a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5ZM5 3.25a.75.75 0 1 0 0 .001Z"


# ------------------------------------------------------------------ fonts

@lru_cache(None)
def _font_b64(kind: str) -> str:
    return base64.b64encode((FONTS / f"archivo-{kind}.woff2").read_bytes()).decode()


@lru_cache(None)
def _metrics(kind: str):
    from fontTools.ttLib import TTFont
    f = TTFont(FONTS / f"archivo-{kind}.woff2")
    cmap, hmtx, upem = f.getBestCmap(), f["hmtx"], f["head"].unitsPerEm
    return cmap, hmtx, upem


def text_width(s: str, kind: str, size: float) -> float:
    try:
        cmap, hmtx, upem = _metrics(kind)
    except Exception:            # fontTools missing: rough estimate
        return len(s) * size * (0.62 if kind == "display" else 0.52)
    w = 0
    for ch in s:
        g = cmap.get(ord(ch)) or cmap.get(ord("?"))
        w += hmtx[g][0]
    return w * size / upem


def fit(s: str, kind: str, size: float, width: float) -> str:
    if text_width(s, kind, size) <= width:
        return s
    while s and text_width(s + "…", kind, size) > width:
        s = s[:-1]
    return s.rstrip(" ,.-:(") + "…"


def wrap(s: str, kind: str, size: float, width: float, max_lines: int) -> list[str]:
    words, lines, cur = s.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if text_width(trial, kind, size) <= width:
            cur = trial
        else:
            lines.append(cur); cur = w
    lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = fit(lines[-1] + " " + " ".join(words), kind, size, width)
    return [l for l in lines if l]


def style(t: dict, kinds=("display", "text", "strong")) -> str:
    faces = "".join(
        f"@font-face{{font-family:{FACES[k]};src:url(data:font/woff2;base64,{_font_b64(k)}) format('woff2');}}"
        for k in kinds)
    return (f"<style>{faces}"
            f".d{{font-family:{FACES['display']},system-ui,sans-serif}}"
            f".t{{font-family:{FACES['text']},system-ui,sans-serif}}"
            f".s{{font-family:{FACES['strong']},system-ui,sans-serif;font-variant-numeric:tabular-nums}}"
            f"</style>")


def T(x, y, s, cls, size, fill, anchor="start", extra=""):
    return (f'<text x="{x:.1f}" y="{y:.1f}" class="{cls}" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}" {extra}>{escape(s)}</text>')


def icon(path, x, y, size, fill):
    k = size / 16
    return f'<path d="{path}" fill="{fill}" transform="translate({x:.1f},{y:.1f}) scale({k:.3f})"/>'


def fmt_stars(n: int) -> str:
    if n >= 100_000:
        return f"{n / 1000:.0f}k"
    if n >= 1000:
        return f"{n / 1000:.1f}k".replace(".0k", "k")
    return str(n)


def svg(w, h, t, body, title, gap=14):
    """A card of w x h with a transparent strip of `gap` px below it, so stacked
    images in the README get breathing room. Everything is clipped to the card."""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h + gap}" viewBox="0 0 {w} {h + gap}" '
            f'role="img" aria-label="{escape(title)}"><title>{escape(title)}</title>{style(t)}'
            f'<defs><clipPath id="card"><rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="10"/></clipPath></defs>'
            f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="10" fill="{t["field"]}"/>'
            f'<g clip-path="url(#card)">{body}</g>'
            f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="10" fill="none" stroke="{t["rule"]}"/></svg>')


# ------------------------------------------------------------------ header

def depth_series(prs: list[dict], start: datetime, end: datetime):
    """Daily steps: cumulative merged, and merged + currently in review."""
    merged = sorted(datetime.fromisoformat(p["pull_request"]["merged_at"][:19]) for p in prs
                    if p.get("pull_request", {}).get("merged_at"))
    review = sorted(datetime.fromisoformat(p["created_at"][:19]) for p in prs if p["state"] == "open")
    pts_m, pts_r = [], []
    day = start
    while day <= end:
        nxt = day + timedelta(days=1)
        m = sum(1 for d in merged if d < nxt)
        r = sum(1 for d in review if d < nxt)
        pts_m.append((day, m)); pts_r.append((day, m + r))
        day = nxt
    return pts_m, pts_r


def header(data: dict, t: dict) -> str:
    W, H = 840, 270
    b = []
    # left column: who, in plain words
    b.append(T(36, 82, data["name"], "d", 40, t["ink"]))
    for i, line in enumerate(wrap(data["summary"], "text", 16, 360, 3)):
        b.append(T(36, 120 + i * 24, line, "t", 16, t["ink"]))
    y0 = 120 + len(wrap(data["summary"], "text", 16, 360, 3)) * 24 + 26
    stats = [(str(data["merged"]), "merged pull requests", t["merged"]),
             (str(data["review"]), "in review", t["review"]),
             (str(data["orgs"]), "organisations", t["slate"])]
    x = 36
    for num, label, col in stats:
        b.append(f'<rect x="{x}" y="{y0 - 22}" width="3" height="40" fill="{col}"/>')
        b.append(T(x + 12, y0 - 1, num, "s", 22, t["ink"]))
        b.append(T(x + 12, y0 + 16, label, "t", 12, t["slate"]))
        x += 12 + max(text_width(label, "text", 12), text_width(num, "strong", 22)) + 28

    # right column: the depth chart
    cx0, cx1, cy0, cy1 = 452, 760, 46, 214
    pts_m, pts_r = data["series"]
    n = len(pts_m)
    top = max(max(v for _, v in pts_r), 1)
    ymax = max(5, top + (5 - top % 5) % 5 + (5 if top % 5 == 0 else 0))

    def X(i): return cx0 + (cx1 - cx0) * i / max(n - 1, 1)
    def Y(v): return cy1 - (cy1 - cy0) * v / ymax

    def steps(pts):
        d = f"M{X(0):.1f},{Y(pts[0][1]):.1f}"
        for i in range(1, n):
            d += f"H{X(i):.1f}V{Y(pts[i][1]):.1f}"
        return d

    for v in range(0, ymax + 1, max(1, ymax // 4)):
        dash = "" if v == 0 else 'stroke-dasharray="2 4"'
        b.append(f'<line x1="{cx0}" x2="{cx1}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="{t["rule"]}" '
                 f'stroke-width="1" {dash}/>')
        b.append(T(cx1 + 10, Y(v) + 4, str(v), "s", 11, t["slate"]))
    area = steps(pts_m) + f"H{X(n - 1):.1f}V{Y(0):.1f}H{X(0):.1f}Z"
    b.append(f'<path d="{area}" fill="{t["merged_fill"]}" fill-opacity="{t["fill_op"]}"/>')
    b.append(f'<path d="{steps(pts_r)}" fill="none" stroke="{t["review"]}" stroke-width="1.6" stroke-dasharray="4 3"/>')
    b.append(f'<path d="{steps(pts_m)}" fill="none" stroke="{t["merged"]}" stroke-width="2.2"/>')
    # month ticks
    seen = set()
    for i, (d, _) in enumerate(pts_m):
        if d.day == 1 or i == 0:
            key = (d.year, d.month)
            if key in seen:
                continue
            seen.add(key)
            if i > 0:
                b.append(f'<line x1="{X(i):.1f}" x2="{X(i):.1f}" y1="{cy1}" y2="{cy1 + 5}" stroke="{t["slate"]}"/>')
            b.append(T(X(i) + (0 if i else 0), cy1 + 20, d.strftime("%b"), "t", 11, t["slate"]))
    # end labels
    mv, rv = pts_m[-1][1], pts_r[-1][1]
    b.append(f'<circle cx="{X(n - 1):.1f}" cy="{Y(mv):.1f}" r="3.5" fill="{t["merged"]}"/>')
    b.append(T(cx0, cy0 - 18, "Merged upstream, with open pull requests stacked on top", "t", 12, t["slate"]))
    return svg(W, H, t, "".join(b), f"{data['name']}: {data['merged']} merged pull requests, {data['review']} in review")


# ------------------------------------------------------------------ tiles

def merged_tile(p: dict, t: dict, wide: bool = False) -> str:
    """p: {repo, stars, merged, titles:[...]}"""
    W, H = (840, 150) if wide else (412, 170)
    owner, name = p["repo"].split("/")
    b = [f'<rect x="0" y="0" width="5" height="{H}" fill="{t["merged"]}"/>']
    right = W - 24
    star_txt = fmt_stars(p["stars"])
    sw = text_width(star_txt, "strong", 15)
    b.append(T(right, 36, star_txt, "s", 15, t["ink"], "end"))
    b.append(icon(STAR, right - sw - 22, 23, 15, t["review"]))
    name_w = right - sw - 40 - 28
    b.append(T(28, 34, owner, "t", 13, t["slate"]))
    b.append(T(28, 68, fit(name, "display", 26 if wide else 23, name_w), "d", 26 if wide else 23, t["ink"]))
    count = f'{p["merged"]} merged pull request{"s" if p["merged"] != 1 else ""}'
    b.append(icon(MERGE, 28, 86, 13, t["merged"]))
    b.append(T(46, 97, count, "s", 13, t["merged"]))
    tw = W - 56
    lines = []
    for title in p["titles"][: (2 if wide else 1)]:
        lines += wrap(title, "text", 13.5, tw, 1 if wide else 2)
    for i, line in enumerate(lines[:2]):
        b.append(T(28, 124 + i * 19, line, "t", 13.5, t["ink"]))
    return svg(W, H, t, "".join(b), f"{p['repo']}: {count}")


SEAL = "M8 0l1.6 1.2 2-.1.6 1.9 1.6 1.2-.6 1.9.6 1.9-1.6 1.2-.6 1.9-2-.1L8 11.2 6.4 10l-2 .1-.6-1.9L2.2 7l.6-1.9-.6-1.9 1.6-1.2.6-1.9 2 .1zM5 12.6l-.9 3.4L6 15l1 1.6.6-3.6zm6 0l-.9 3.4L12 15l1 1.6.6-3.6z"


def rosette(x: float, y: float, size: float, fill: str, field: str) -> str:
    """Award rosette: a medal with two ribbon tails. (x, y) is the top-left corner."""
    r = size * 0.34
    cx, cy = x + size / 2, y + r + 1
    tail_w, top, bot = size * 0.2, cy + r * 0.55, y + size
    return (f'<path d="M{cx - tail_w * 1.6:.1f},{top:.1f}L{cx - tail_w * 1.9:.1f},{bot:.1f}'
            f'L{cx - tail_w * 0.9:.1f},{bot - size * 0.12:.1f}L{cx - tail_w * 0.4:.1f},{bot:.1f}L{cx - tail_w * 0.1:.1f},{top:.1f}Z" fill="{fill}"/>'
            f'<path d="M{cx + tail_w * 1.6:.1f},{top:.1f}L{cx + tail_w * 1.9:.1f},{bot:.1f}'
            f'L{cx + tail_w * 0.9:.1f},{bot - size * 0.12:.1f}L{cx + tail_w * 0.4:.1f},{bot:.1f}L{cx + tail_w * 0.1:.1f},{top:.1f}Z" fill="{fill}"/>'
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}"/>'
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r * 0.55:.1f}" fill="none" stroke="{field}" stroke-width="{max(1, size / 14):.1f}"/>')


def project_tile(p: dict, t: dict, wide: bool = False) -> str:
    W, H = (840, 150) if wide else (412, 160)
    b = [f'<rect x="0" y="0" width="5" height="{H}" fill="{t["own"]}"/>']
    b.append(T(28, 34, p["tech"], "t", 13, t["slate"]))
    right = W - 24
    if p.get("patent"):
        label = "Patent published"
        lw = text_width(label, "strong", 12.5)
        b.append(T(right, 34, label, "s", 12.5, t["own"], "end"))
        b.append(rosette(right - lw - 20, 20, 15, t["own"], t["field"]))
    elif p.get("stars"):
        b.append(T(right, 34, fmt_stars(p["stars"]), "s", 13, t["ink"], "end"))
    size = 24 if wide else 21
    b.append(T(28, 68 if wide else 66, fit(p["title"], "display", size, W - 56), "d", size, t["ink"]))
    width = (W - 56) if not wide else 620
    for i, line in enumerate(wrap(p["blurb"], "text", 14 if wide else 13.5, width, 3)):
        b.append(T(28, (100 if wide else 96) + i * 20, line, "t", 14 if wide else 13.5, t["ink"]))
    return svg(W, H, t, "".join(b), f"{p['title']}: {p['blurb']}")


def patents_card(items: list[dict], t: dict) -> str:
    """items: [{title, number, tech}] -> one card listing the applications."""
    W, row = 840, 64
    H = 30 + row * len(items) + 8
    b = []
    for i, it in enumerate(items):
        y = 30 + i * row
        if i:
            b.append(f'<line x1="28" x2="{W - 28}" y1="{y - 10}" y2="{y - 10}" stroke="{t["rule"]}"/>')
        b.append(rosette(28, y + 2, 24, t["own"], t["field"]))
        b.append(T(66, y + 18, fit(it["title"], "display", 18, 520), "d", 18, t["ink"]))
        b.append(T(66, y + 38, it["tech"], "t", 13, t["slate"]))
        b.append(T(W - 28, y + 14, "Application no.", "t", 12, t["slate"], "end"))
        b.append(T(W - 28, y + 36, it["number"], "s", 19, t["ink"], "end", 'letter-spacing="0.5"'))
    return svg(W, H, t, "".join(b), "Patent applications: " + ", ".join(f"{i['title']} {i['number']}" for i in items))


# ------------------------------------------------------------------ open-source panel

def oss_panel(totals: dict, rows: list[dict], t: dict) -> str:
    """totals: merged, review, orgs, repos. rows: [{repo, desc, stars, merged, review, closed}]"""
    W = 840
    top, row_h = 122, 56
    H = top + row_h * len(rows) + 14
    b = []
    cols = [("merged", "merged upstream", t["merged"]), ("review", "in review", t["review"]),
            ("orgs", "organisations", t["ink"]), ("repos", "repositories", t["ink"])]
    for i, (k, label, col) in enumerate(cols):
        x = 32 + i * 200
        b.append(T(x, 62, str(totals[k]), "d", 36, col))
        b.append(T(x, 86, label, "t", 13, t["slate"]))
    b.append(f'<line x1="32" x2="{W - 32}" y1="{top - 14}" y2="{top - 14}" stroke="{t["rule"]}"/>')
    bx0, bx1 = 452, 690
    scale = max((r["merged"] + r["review"] + r["closed"]) for r in rows) if rows else 1
    for i, r in enumerate(rows):
        y = top + i * row_h
        name_w = 300
        name = fit(r["repo"], "strong", 15, name_w)
        b.append(T(32, y + 18, name, "s", 15, t["ink"]))
        sx = 32 + text_width(name, "strong", 15) + 12
        if r["stars"]:
            b.append(icon(STAR, sx, y + 6, 12, t["review"]))
            b.append(T(sx + 16, y + 17, fmt_stars(r["stars"]), "s", 12, t["slate"]))
        if r.get("desc"):
            b.append(T(32, y + 38, fit(r["desc"], "text", 12.5, 390), "t", 12.5, t["slate"]))
        # stacked bar
        b.append(f'<rect x="{bx0}" y="{y + 10}" width="{bx1 - bx0}" height="7" rx="3.5" fill="{t["rule"]}" fill-opacity="0.45"/>')
        x = bx0
        for k, col in (("merged", t["merged"]), ("review", t["review"]), ("closed", t["slate"])):
            if r[k]:
                w = (bx1 - bx0) * r[k] / scale
                op = ' fill-opacity="0.55"' if k == "closed" else ""
                b.append(f'<rect x="{x:.1f}" y="{y + 10}" width="{max(w - 2, 3):.1f}" height="7" rx="3.5" fill="{col}"{op}/>')
                x += w
        b.append(T(W - 32, y + 18, f"{r['merged']} merged", "s", 13, t["merged"] if r["merged"] else t["slate"], "end"))
        sub = (f"{r['review']} in review" if r["review"] else
               f"{r['closed']} closed" if r["closed"] else "no open work")
        b.append(T(W - 32, y + 37, sub, "t", 12, t["review"] if r["review"] else t["slate"], "end"))
    return svg(W, H, t, "".join(b), f"Open source: {totals['merged']} merged, {totals['review']} in review "
                                     f"across {totals['orgs']} organisations")


# ------------------------------------------------------------------ metric-led project card

def pill(x_right: float, y: float, label: str, col: str, t: dict) -> str:
    w = text_width(label, "strong", 11.5) + 30
    x = x_right - w
    return (f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="22" rx="11" fill="{col}" fill-opacity="0.12"/>'
            f'<circle cx="{x + 12:.1f}" cy="{y + 11}" r="3.5" fill="{col}"/>'
            + T(x + 21, y + 15.5, label, "s", 11.5, col))


def metric_card(p: dict, t: dict, wide: bool = False) -> str:
    W, H = (840, 200) if wide else (412, 196)
    b = [f'<rect x="0" y="0" width="5" height="{H}" fill="{t["own"]}"/>']
    status = p.get("status")
    col = {"Patent published": t["own"], "Live": t["merged"], "Benchmarked": t["merged"]}.get(status, t["slate"])
    pw = (text_width(status, "strong", 11.5) + 40) if status else 0
    b.append(T(28, 36, fit(p["title"], "display", 16, W - 56 - pw), "d", 16, t["ink"]))
    if status:
        if status == "Patent published":
            w = text_width(status, "strong", 11.5) + 34
            x = W - 24 - w
            b.append(f'<rect x="{x:.1f}" y="19" width="{w:.1f}" height="22" rx="11" fill="{col}" fill-opacity="0.12"/>')
            b.append(rosette(x + 6, 22, 15, col, t["field"]))
            b.append(T(x + 25, 34.5, status, "s", 11.5, col))
        else:
            b.append(pill(W - 24, 19, status, col, t))
    big, unit = p["metric"], p.get("unit", "")
    bs = 44 if wide else 38
    b.append(T(28, 96, big, "d", bs, t["ink"]))
    if unit:
        b.append(T(28 + text_width(big, "display", bs) + 10, 96, unit, "t", 16, t["slate"]))
    lines = wrap(p["blurb"], "text", 13.5, (W - 56) if not wide else 760, 2)
    for i, line in enumerate(lines):
        b.append(T(28, 124 + i * 19, line, "t", 13.5, t["ink"]))
    fy = H - 22
    b.append(f'<line x1="28" x2="{W - 24}" y1="{fy - 18}" y2="{fy - 18}" stroke="{t["rule"]}"/>')
    b.append(T(28, fy, p["tech"], "t", 12, t["slate"]))
    return svg(W, H, t, "".join(b), f"{p['title']}: {big} {unit}. {p['blurb']}")
