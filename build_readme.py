#!/usr/bin/env python3
"""Rebuild the profile README and its images from the GitHub API.

    python build_readme.py            # reads profile.json, writes assets/*.svg and README.md

Everything between <!-- OSS:START --> and <!-- OSS:END --> is generated.
Text outside the markers is left alone. Edit profile.json to change your
name, summary or featured projects.
"""
from __future__ import annotations

import html
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
          max_rows: int = 10) -> str:
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

    # per-project rows: merged / in review / closed
    groups: dict[str, dict] = {}
    for p in outside:
        r = repo_of(p)
        g = groups.setdefault(r, {"repo": r, "merged": 0, "review": 0, "closed": 0,
                                  "stars": info.get(r.lower(), {}).get("stargazers_count", 0),
                                  "desc": (info.get(r.lower(), {}).get("description") or "").strip()})
        if p.get("pull_request", {}).get("merged_at"):
            g["merged"] += 1
        elif p["state"] == "open":
            g["review"] += 1
        else:
            g["closed"] += 1
    rows = sorted(groups.values(), key=lambda g: (g["merged"], g["review"], g["stars"]), reverse=True)[:max_rows]
    totals = {"merged": len(merged), "review": len(review),
              "orgs": hdr["orgs"], "repos": len(groups)}

    md = [START, "", picture("header", f"{cfg['name']}: {len(merged)} merged pull requests, {len(review)} in review", "100%"), ""]
    if cfg.get("about"):
        md += ["### About me", ""]
        for para in cfg["about"]:
            md += [para, ""]
    if rows:
        md += ["### Open source", ""]
        for th, t in render.THEMES.items():
            files[f"opensource-{th}.svg"] = render.oss_panel(totals, rows, t)
        md += [f'<a href="https://github.com/pulls?q=' + urllib.parse.quote(f"is:pr author:{user}")
               + f'">{picture("opensource", f"{len(merged)} merged, {len(review)} in review", "100%")}</a>', ""]

        def item(p, when, verb):
            title = p["title"] if len(p["title"]) <= 80 else p["title"][:80].rsplit(" ", 1)[0] + "…"
            return (f'<li><a href="{p["html_url"]}"><code>{repo_of(p)}#{p["number"]}</code></a> '
                    f'{html.escape(title)} <sub>{verb} {when[:10]}</sub></li>')
        recent = sorted(merged, key=lambda p: p["pull_request"]["merged_at"], reverse=True)
        opened = sorted(review, key=lambda p: p["created_at"], reverse=True)
        left = "".join(item(p, p["pull_request"]["merged_at"], "merged") for p in recent[:5])
        right = "".join(item(p, p["created_at"], "opened") for p in opened[:5])
        if len(recent) > 5:
            left += f"<li>and {len(recent) - 5} more merged</li>"
        if len(opened) > 5:
            right += f"<li>and {len(opened) - 5} more open</li>"
        md += ['<table><tr><th align="left" width="50%">Recently merged</th>'
               '<th align="left" width="50%">In review now</th></tr>',
               f'<tr><td valign="top"><ul>{left}</ul></td><td valign="top"><ul>{right or "<li>Nothing open</li>"}</ul></td></tr></table>', ""]

    feats = cfg.get("featured", [])
    if feats:
        md += ["### Things I've built", ""]
        for f in feats:
            meta = info.get(f["repo"].lower(), {})
            f = {**f, "stars": meta.get("stargazers_count", 0)}
            stem = f"project-{slug(f['repo'].split('/')[1])}"
            wide = bool(f.get("wide"))
            for th, t in render.THEMES.items():
                files[f"{stem}-{th}.svg"] = (render.metric_card(f, t, wide=wide) if f.get("metric")
                                             else render.project_tile(f, t, wide=wide))
            alt = f["title"] + (f" (patent published, application no. {f['patent']})" if f.get("patent") else "")
            md.append(f'<a href="https://github.com/{f["repo"]}">{picture(stem, alt, "100%" if wide else "49%")}</a>')
            if wide:
                md.append("")
        md.append("")
    pats = [{"title": f.get("patent_title", f["title"]), "number": f["patent"], "tech": f["tech"]}
            for f in feats if f.get("patent")]
    if pats:
        md += [f"### {cfg.get('patents_heading', 'Patent applications')}", ""]
        for th, t in render.THEMES.items():
            files[f"patents-{th}.svg"] = render.patents_card(pats, t)
        alt = "; ".join(f"{p['title']}: application no. {p['number']}" for p in pats)
        md += [picture("patents", alt, "100%"), ""]
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
