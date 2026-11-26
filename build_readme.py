#!/usr/bin/env python3
"""Rebuild the profile README and its images from the GitHub API.

    python build_readme.py            # reads profile.json, writes assets/*.svg and README.md

Everything between <!-- OSS:START --> and <!-- OSS:END --> is generated.
Text outside the markers is left alone. Edit profile.json to change your
name, summary or featured projects.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import render

HERE = Path(__file__).resolve().parent
API = "https://api.github.com"
START, END = "<!-- OSS:START -->", "<!-- OSS:END -->"


def get(path: str, **params):
    url = f"{API}{path}?{urllib.parse.urlencode(params)}"
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-readme"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
        return json.loads(r.read().decode())


def search_prs(user: str) -> list[dict]:
    out, page = [], 1
    while True:
        items = get("/search/issues", q=f"is:pr author:{user}", per_page=100, page=page).get("items", [])
        out += items
        if len(items) < 100 or page >= 10:
            return out
        page += 1


def repo_info(repos: set[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    repos = sorted(repos)
    for i in range(0, len(repos), 5):
        q = " ".join(f"repo:{r}" for r in repos[i:i + 5])
        try:
            for it in get("/search/repositories", q=q, per_page=10).get("items", []):
                out[it["full_name"].lower()] = it
        except Exception as e:
            print(f"repo lookup failed for {repos[i:i + 5]}: {e}", file=sys.stderr)
    return out


def repo_of(p: dict) -> str:
    return p["repository_url"].split("/repos/")[1]


def picture(stem: str, alt: str, width: str) -> str:
    return (f'<picture><source media="(prefers-color-scheme: dark)" srcset="assets/{stem}-dark.svg">'
            f'<img src="assets/{stem}-light.svg" alt="{alt}" width="{width}"></picture>')


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def build(cfg: dict, prs: list[dict], info: dict, now: datetime, out_dir: Path,
          max_tiles: int = 7, min_stars: int = 50) -> str:
    user = cfg["user"]
    outside = [p for p in prs if repo_of(p).split("/")[0].lower() != user.lower()]
    merged = [p for p in outside if p.get("pull_request", {}).get("merged_at")]
    review = [p for p in outside if p["state"] == "open"]

    # header data
    first = min((datetime.fromisoformat(p["created_at"][:19]) for p in outside), default=now.replace(tzinfo=None))
    start = (first - timedelta(days=3)).replace(hour=0, minute=0, second=0, microsecond=0)
    end = now.replace(tzinfo=None)
    series = render.depth_series(outside, start, end)
    hdr = {"name": cfg["name"], "summary": cfg["summary"], "merged": len(merged), "review": len(review),
           "orgs": len({repo_of(p).split("/")[0].lower() for p in merged}), "series": series}

    files: dict[str, str] = {}
    for th, t in render.THEMES.items():
        files[f"header-{th}.svg"] = render.header(hdr, t)

    # merged tiles, grouped by project, biggest first
    groups: dict[str, dict] = {}
    for p in sorted(merged, key=lambda p: p["pull_request"]["merged_at"], reverse=True):
        r = repo_of(p)
        g = groups.setdefault(r, {"repo": r, "stars": info.get(r.lower(), {}).get("stargazers_count", 0),
                                  "merged": 0, "titles": []})
        g["merged"] += 1
        g["titles"].append(p["title"])
    tiles = sorted((g for g in groups.values() if g["stars"] >= min_stars),
                   key=lambda g: (g["stars"], g["merged"]), reverse=True)[:max_tiles]

    md = [START, "", picture("header", f"{cfg['name']}: {len(merged)} merged pull requests, {len(review)} in review", "100%"), ""]
    if tiles:
        md += ["### Merged upstream", ""]
        for i, g in enumerate(tiles):
            stem = f"merged-{slug(g['repo'])}"
            wide = i == 0
            for th, t in render.THEMES.items():
                files[f"{stem}-{th}.svg"] = render.merged_tile(g, t, wide=wide)
            link = (f"https://github.com/{g['repo']}/pulls?q="
                    + urllib.parse.quote(f"is:pr author:{user} is:merged"))
            md.append(f'<a href="{link}">{picture(stem, g["repo"], "100%" if wide else "49%")}</a>')
            if wide:
                md.append("")
        md.append("")
    if review:
        md += ["### In review", ""]
        for p in sorted(review, key=lambda p: info.get(repo_of(p).lower(), {}).get("stargazers_count", 0),
                        reverse=True)[:6]:
            title = p["title"] if len(p["title"]) <= 90 else p["title"][:90].rsplit(" ", 1)[0] + "…"
            md.append(f"- [{repo_of(p)}#{p['number']}]({p['html_url']}): {title}")
        md.append("")
    feats = cfg.get("featured", [])
    if feats:
        md += ["### Things I've built", ""]
        for f in feats:
            meta = info.get(f["repo"].lower(), {})
            f = {**f, "stars": meta.get("stargazers_count", 0)}
            stem = f"project-{slug(f['repo'].split('/')[1])}"
            for th, t in render.THEMES.items():
                files[f"{stem}-{th}.svg"] = render.project_tile(f, t)
            md.append(f'<a href="https://github.com/{f["repo"]}">{picture(stem, f["title"], "49%")}</a>')
        md.append("")
    md += [f"<sub>Rebuilt from the GitHub API every six hours. Last update {now:%Y-%m-%d}.</sub>", "", END]

    out_dir.mkdir(exist_ok=True)
    keep = set(files)
    for old in out_dir.glob("*.svg"):
        if old.name not in keep:
            old.unlink()
    for name, content in files.items():
        (out_dir / name).write_text(content)
    return "\n".join(md)


def splice(readme: str, section: str) -> str:
    if START in readme and END in readme:
        return re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: section, readme, flags=re.S)
    return section + "\n\n" + readme


def main() -> None:
    cfg = json.loads((HERE / "profile.json").read_text())
    prs = search_prs(cfg["user"])
    repos = {repo_of(p) for p in prs} | {f["repo"] for f in cfg.get("featured", [])}
    section = build(cfg, prs, repo_info(repos), datetime.now(timezone.utc), HERE / "assets")
    path = HERE / "README.md"
    old = path.read_text() if path.exists() else ""
    new = splice(old, section)
    if new != old:
        path.write_text(new)
    print(f"README {'updated' if new != old else 'unchanged'}; {len(list((HERE / 'assets').glob('*.svg')))} images")


if __name__ == "__main__":
    main()
