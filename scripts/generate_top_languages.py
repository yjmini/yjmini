#!/usr/bin/env python3
"""Generate a GitHub top-languages SVG for the yjmini profile README.

The card intentionally mirrors the portfolio-oriented GitHub README Stats setup:
- owner: yjmini
- excludes notebook-heavy learning/archive repositories
- ranking_index = (byte_count ** 0.5) * (repo_count ** 0.5)
- percentages are normalized across the displayed top 5 languages
"""

from __future__ import annotations

import html
import json
import os
import sys
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

OWNER = "yjmini"
EXCLUDE_REPOS = {"yjmini", "deepLearning24-2", "DL_24_2", "DL24-2", "RL_HuggingFace"}
TOP_N = 5
SIZE_WEIGHT = 0.5
COUNT_WEIGHT = 0.5
OUT_PATH = Path(__file__).resolve().parents[1] / "assets" / "top-languages.svg"

LANG_COLORS = {
    "Python": "#3572A5",
    "C++": "#f34b7d",
    "Java": "#b07219",
    "Jupyter Notebook": "#DA5B0B",
    "Vue": "#41b883",
    "HTML": "#e34c26",
    "JavaScript": "#f1e05a",
    "ShaderLab": "#222c37",
    "C#": "#178600",
    "Rust": "#dea584",
    "C": "#555555",
}


def request_json(url: str):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "yjmini-profile-readme-generator",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def github_pages(url: str):
    page = 1
    while True:
        sep = "&" if "?" in url else "?"
        data = request_json(f"{url}{sep}per_page=100&page={page}")
        if not data:
            break
        yield from data
        if len(data) < 100:
            break
        page += 1


def collect_languages():
    bytes_by_lang: Counter[str] = Counter()
    repo_count_by_lang: Counter[str] = Counter()

    repos = github_pages(f"https://api.github.com/users/{OWNER}/repos?type=owner&sort=updated")
    for repo in repos:
        name = repo["name"]
        if repo.get("fork") or repo.get("private") or name in EXCLUDE_REPOS:
            continue

        languages = request_json(f"https://api.github.com/repos/{OWNER}/{name}/languages")
        for lang, byte_count in languages.items():
            if byte_count <= 0:
                continue
            bytes_by_lang[lang] += byte_count
            repo_count_by_lang[lang] += 1

    if not bytes_by_lang:
        raise RuntimeError("No language data returned from GitHub API")

    scores = {
        lang: (bytes_by_lang[lang] ** SIZE_WEIGHT) * (repo_count_by_lang[lang] ** COUNT_WEIGHT)
        for lang in bytes_by_lang
    }
    top = sorted(scores, key=lambda lang: scores[lang], reverse=True)[:TOP_N]
    denominator = sum(scores[lang] for lang in top)

    return [
        {
            "name": lang,
            "bytes": bytes_by_lang[lang],
            "repo_count": repo_count_by_lang[lang],
            "score": scores[lang],
            "percent": scores[lang] / denominator * 100,
            "color": LANG_COLORS.get(lang, "#858585"),
        }
        for lang in top
    ]


def svg_text(x: float, y: float, text: str, cls: str = "lang-name", anchor: str = "start") -> str:
    return f'<text x="{x}" y="{y}" class="{cls}" text-anchor="{anchor}">{html.escape(text)}</text>'


def render_svg(languages) -> str:
    width = 350
    height = 170
    bar_x = 25
    bar_y = 55
    bar_w = 300
    bar_h = 8
    item_y0 = 88
    item_gap = 18

    # Top segmented bar, normalized to displayed languages.
    rects = []
    cursor = 0.0
    for idx, lang in enumerate(languages):
        seg_w = bar_w * lang["percent"] / 100
        # Let the final segment absorb rounding so the bar ends cleanly.
        if idx == len(languages) - 1:
            seg_w = bar_w - cursor
        rects.append(
            f'<rect x="{bar_x + cursor:.2f}" y="{bar_y}" width="{seg_w:.2f}" height="{bar_h}" fill="{lang["color"]}" />'
        )
        cursor += seg_w

    items = []
    for idx, lang in enumerate(languages):
        y = item_y0 + idx * item_gap
        name = lang["name"]
        pct = f'{lang["percent"]:.2f}%'
        items.append(f'<circle cx="{bar_x + 5}" cy="{y - 4}" r="5" fill="{lang["color"]}" />')
        items.append(svg_text(bar_x + 16, y, f"{name} {pct}"))

    # Keep title/text styling close to the current GitHub README Stats tokyonight card.
    return f'''<svg width="350" height="170" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc">
  <title id="title">Most Used Languages</title>
  <desc id="desc">Top languages for yjmini after excluding notebook-heavy learning repositories and using size/count balanced weighting.</desc>
  <style>
    .header {{ font: 600 18px 'Segoe UI', Ubuntu, Sans-Serif; fill: #70a5fd; }}
    .lang-name {{ font: 400 11px 'Segoe UI', Ubuntu, Sans-Serif; fill: #38bdae; }}
  </style>
  <rect x="0.5" y="0.5" rx="4.5" height="169" width="349" fill="#0d1117" stroke="#E4E2E2" stroke-opacity="0" />
  <text x="25" y="35" class="header">Most Used Languages</text>
  <clipPath id="bar-clip"><rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" rx="5" /></clipPath>
  <g clip-path="url(#bar-clip)">
    {''.join(rects)}
  </g>
  {''.join(items)}
</svg>
'''


def main() -> int:
    languages = collect_languages()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(render_svg(languages), encoding="utf-8")
    for lang in languages:
        print(f'{lang["name"]}: {lang["percent"]:.2f}% bytes={lang["bytes"]} repos={lang["repo_count"]}')
    print(f"Wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.HTTPError as exc:
        print(f"GitHub API error: HTTP {exc.code} {exc.reason}", file=sys.stderr)
        print(exc.read().decode("utf-8", errors="replace"), file=sys.stderr)
        raise
