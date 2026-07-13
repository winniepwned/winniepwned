#!/usr/bin/env python3
"""
entropy.py — winniepwned's entropy report

Measures the Shannon entropy of a GitHub user's contribution patterns
and renders it as an SVG in catppuccin mocha / jetbrains mono.

The bear does not count his commits. He asks how surprising they are.

stdlib only. no dependencies. run nightly from a GitHub Action.
"""

import json
import math
import os
import random
import sys
import urllib.request
from collections import Counter
from datetime import datetime, timezone

USER = os.environ.get("GH_USER", "winniepwned")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = os.environ.get("OUT", "dist/entropy.svg")

# ── catppuccin mocha ────────────────────────────────────────────────
BASE     = "#1e1e2e"
SURFACE  = "#313244"
OVERLAY  = "#6c7086"
SUBTEXT  = "#a6adc8"
TEXT     = "#cdd6f4"
MAUVE    = "#cba6f7"
PINK     = "#f5c2e7"
LAVENDER = "#b4befe"
MONO     = "JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, monospace"

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


# ── entropy ─────────────────────────────────────────────────────────
def shannon(counts):
    """Shannon entropy in bits. Returns (H, H_max)."""
    total = sum(counts)
    if total <= 0:
        return 0.0, 0.0
    h = 0.0
    for c in counts:
        if c > 0:
            p = c / total
            h -= p * math.log2(p)
    n = sum(1 for c in counts if c > 0)
    return h, math.log2(len(counts)) if len(counts) > 1 else 0.0


# ── github ──────────────────────────────────────────────────────────
def gql(query, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={
            "Authorization": f"bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "entropy-bear",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


QUERY = """
query($user: String!) {
  user(login: $user) {
    contributionsCollection {
      contributionCalendar {
        weeks {
          contributionDays { date contributionCount weekday }
        }
      }
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
      nodes {
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
  }
}
"""


def collect():
    """Returns (weekday_counts, daily_counts, language_sizes)."""
    data = gql(QUERY, {"user": USER})
    if "errors" in data:
        raise RuntimeError(data["errors"])
    u = data["data"]["user"]

    weekday = [0] * 7
    daily = []
    weeks = u["contributionsCollection"]["contributionCalendar"]["weeks"]
    for w in weeks:
        for d in w["contributionDays"]:
            c = d["contributionCount"]
            daily.append(c)
            # GitHub: weekday 0 = Sunday. Shift so 0 = Monday.
            weekday[(d["weekday"] - 1) % 7] += c

    langs = Counter()
    for repo in u["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            langs[e["node"]["name"]] += e["size"]

    return weekday, daily, langs


# ── svg ─────────────────────────────────────────────────────────────
def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def noise_band(x, y, w, h, cols, seed):
    """The bear's fire: a band of pure disorder, reseeded every night."""
    rng = random.Random(seed)
    cell = w / cols
    rows = max(1, int(h / cell))
    out = []
    for r in range(rows):
        for c in range(cols):
            v = rng.random()
            if v < 0.34:
                continue
            op = round(0.08 + (v ** 3) * 0.92, 3)
            col = MAUVE if v > 0.88 else (LAVENDER if v > 0.66 else SURFACE)
            out.append(
                f'<rect x="{x + c * cell:.2f}" y="{y + r * cell:.2f}" '
                f'width="{cell - 1.2:.2f}" height="{cell - 1.2:.2f}" rx="1" '
                f'fill="{col}" opacity="{op}"/>'
            )
    return "\n".join(out)


def meter(x, y, w, label, h, hmax, note):
    """One entropy bar: measured against maximum possible disorder."""
    ratio = (h / hmax) if hmax > 0 else 0.0
    ratio = max(0.0, min(1.0, ratio))
    bar_w = w - 250
    filled = bar_w * ratio
    segs = 40
    seg_w = bar_w / segs
    lit = int(round(segs * ratio))

    cells = []
    for i in range(segs):
        col = MAUVE if i < lit else SURFACE
        op = 1.0 if i < lit else 0.45
        cells.append(
            f'<rect x="{x + 96 + i * seg_w:.2f}" y="{y - 8}" '
            f'width="{seg_w - 1.6:.2f}" height="11" rx="1" '
            f'fill="{col}" opacity="{op}"/>'
        )

    return f"""
<g>
  <text x="{x}" y="{y + 1}" font-family="{MONO}" font-size="12" fill="{SUBTEXT}">{esc(label)}</text>
  {''.join(cells)}
  <text x="{x + w - 138}" y="{y + 1}" font-family="{MONO}" font-size="12" fill="{TEXT}">{h:.2f}</text>
  <text x="{x + w - 100}" y="{y + 1}" font-family="{MONO}" font-size="12" fill="{OVERLAY}">/ {hmax:.2f} bits</text>
  <text x="{x + 96}" y="{y + 18}" font-family="{MONO}" font-size="9.5" fill="{OVERLAY}">{esc(note)}</text>
</g>"""


def render(weekday, daily, langs, when):
    W, H = 840, 300
    seed = when.strftime("%Y-%m-%d")

    h_wd, max_wd = shannon(weekday)
    h_day, max_day = shannon(daily)
    lang_sizes = [v for _, v in langs.most_common(8)]
    h_lang, max_lang = shannon(lang_sizes)

    total = sum(weekday)
    overall = (
        (h_wd / max_wd if max_wd else 0)
        + (h_day / max_day if max_day else 0)
        + (h_lang / max_lang if max_lang else 0)
    ) / 3

    if overall > 0.86:
        verdict = "the bear is unpredictable. good."
    elif overall > 0.68:
        verdict = "the bear has habits. the bear is aware of this."
    else:
        verdict = "the bear is a creature of routine. this is a vulnerability."

    top_langs = ", ".join(k.lower() for k, _ in langs.most_common(4)) or "—"

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="entropy report">',
        f'<rect width="{W}" height="{H}" rx="10" fill="{BASE}"/>',
        f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="10" fill="none" stroke="{SURFACE}"/>',

        # header
        f'<text x="28" y="38" font-family="{MONO}" font-size="14" font-weight="600" fill="{MAUVE}">$ entropy --user {esc(USER)}</text>',
        f'<text x="{W-28}" y="38" text-anchor="end" font-family="{MONO}" font-size="11" fill="{OVERLAY}">{seed}</text>',

        # the fire
        f'<text x="28" y="66" font-family="{MONO}" font-size="9.5" fill="{OVERLAY}">/dev/urandom — where the bear goes to think</text>',
        noise_band(28, 74, W - 56, 34, 92, seed),

        # meters
        meter(28, 148, W - 56, "weekdays", h_wd, max_wd, f"{esc(sum(weekday))} contributions across 7 days"),
        meter(28, 194, W - 56, "the year", h_day, max_day, f"{esc(len(daily))} days observed"),
        meter(28, 240, W - 56, "languages", h_lang, max_lang, esc(top_langs)),

        # verdict
        f'<line x1="28" y1="264" x2="{W-28}" y2="264" stroke="{SURFACE}"/>',
        f'<text x="28" y="283" font-family="{MONO}" font-size="11" fill="{PINK}">{esc(verdict)}</text>',
        f'<text x="{W-28}" y="283" text-anchor="end" font-family="{MONO}" font-size="11" fill="{OVERLAY}">disorder: {overall*100:.0f}%</text>',
        "</svg>",
    ]
    return "\n".join(parts)


def main():
    when = datetime.now(timezone.utc)
    if "--demo" in sys.argv:
        rng = random.Random(7)
        weekday = [rng.randint(60, 190) for _ in range(7)]
        daily = [max(0, int(rng.gauss(2.2, 2.6))) for _ in range(365)]
        langs = Counter({"Python": 480000, "HCL": 210000, "Shell": 96000,
                         "Dockerfile": 21000, "Jupyter Notebook": 74000})
    else:
        if not TOKEN:
            sys.exit("GITHUB_TOKEN missing")
        weekday, daily, langs = collect()

    svg = render(weekday, daily, langs, when)
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"wrote {OUT} ({len(svg)} bytes)")


if __name__ == "__main__":
    main()