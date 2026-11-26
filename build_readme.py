#!/usr/bin/env python3
"""Rebuild the open-source section of a GitHub profile README.

Standalone (standard library only) so it can run as a GitHub Action in your
profile repo (github.com/<you>/<you>). It replaces only the text between
<!-- OSS:START --> and <!-- OSS:END -->, so the rest of your README stays yours.

Usage:
    python build_readme.py --user AryanSingh2029 --readme README.md
    GITHUB_TOKEN=... python build_readme.py --user AryanSingh2029 --readme README.md

Every number comes from GitHub search at build time, so it never drifts from the truth.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

API = "https://api.github.com"
START, END = "<!-- OSS:START -->", "<!-- OSS:END -->"


def get(path: str, **params):
    url = f"{API}{path}?{urllib.parse.urlencode(params)}"
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-readme"}
    tok = os.environ.get("GITHUB_TOKEN")
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
        return json.loads(r.read().decode())


def search_prs(q: str, limit: int = 1000) -> list[dict]:
    out, page = [], 1
    while len(out) < limit:
        data = get("/search/issues", q=q, per_page=100, page=page)
        out += data.get("items", [])
        if len(data.get("items", [])) < 100:
            break
        page += 1
    return out


def stars_of(repos: set[str]) -> dict[str, int]:
    """Stars for many repos, 5 per search query to stay well inside rate limits."""
    out: dict[str, int] = {}
    repos = sorted(repos)
    for i in range(0, len(repos), 5):
        q = " ".join(f"repo:{r}" for r in repos[i:i + 5])
        try:
            for it in get("/search/repositories", q=q, per_page=10).get("items", []):
                out[it["full_name"].lower()] = it["stargazers_count"]
        except Exception as e:
            print(f"stars lookup failed for {repos[i:i + 5]}: {e}", file=sys.stderr)
    return out


def fmt_stars(n: int) -> str:
    return f"{n / 1000:.1f}k".replace(".0k", "k") if n >= 1000 else str(n)


def build(prs: list[dict], stars: dict[str, int], user: str, now: datetime,
          max_rows: int = 12, min_stars: int = 50) -> str:
    def repo(p):
        return p["repository_url"].split("/repos/")[1]

    outside = [p for p in prs if repo(p).split("/")[0].lower() != user.lower()]
    merged = [p for p in outside if p.get("pull_request", {}).get("merged_at")]
    review = [p for p in outside if p["state"] == "open"]
    orgs = {repo(p).split("/")[0].lower() for p in merged}
    merged_repos = {repo(p) for p in merged}

    def s(p):
        return stars.get(repo(p).lower(), 0)

    lines = [START, ""]
    lines.append(f"**{len(merged)} pull requests merged** into {len(merged_repos)} projects "
                 f"across {len(orgs)} organisations, **{len(review)} in review**.")
    big = sorted({repo(p) for p in merged if s(p) >= 1000}, key=lambda r: -stars.get(r.lower(), 0))
    if big:
        lines.append("")
        lines.append("Merged into " + ", ".join(f"**{r}** ({fmt_stars(stars[r.lower()])}★)" for r in big[:6]) + ".")

    shown = sorted([p for p in merged if s(p) >= min_stars],
                   key=lambda p: (s(p), p["pull_request"]["merged_at"]), reverse=True)[:max_rows]
    if shown:
        lines += ["", "### Merged upstream", "", "| Project | Change | Merged |", "|---|---|---|"]
        for p in shown:
            title = re.sub(r"[|\n]", " ", p["title"])[:90]
            lines.append(f"| [{repo(p)}](https://github.com/{repo(p)}) {fmt_stars(s(p))}★ "
                         f"| [{title}]({p['html_url']}) | {p['pull_request']['merged_at'][:10]} |")
    rv = sorted(review, key=lambda p: s(p), reverse=True)[:5]
    if rv:
        lines += ["", "### In review", ""]
        lines += [f"- [{repo(p)}#{p['number']}]({p['html_url']}): {p['title'][:90]}" for p in rv]
    lines += ["", f"<sub>Built from the GitHub API on {now:%Y-%m-%d}.</sub>", "", END]
    return "\n".join(lines)


def splice(readme: str, section: str) -> str:
    if START in readme and END in readme:
        return re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: section, readme, flags=re.S)
    return readme.rstrip() + "\n\n## Open source\n\n" + section + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", required=True)
    ap.add_argument("--readme", default="README.md")
    ap.add_argument("--min-stars", type=int, default=50, help="hide merges into tiny repos from the table")
    a = ap.parse_args()
    prs = search_prs(f"is:pr author:{a.user}")
    repos = {p["repository_url"].split("/repos/")[1] for p in prs}
    section = build(prs, stars_of(repos), a.user, datetime.now(timezone.utc), min_stars=a.min_stars)
    path = a.readme
    old = open(path).read() if os.path.exists(path) else f"# Hi, I'm {a.user}\n"
    new = splice(old, section)
    if new != old:
        open(path, "w").write(new)
        print("README updated")
    else:
        print("README unchanged")


if __name__ == "__main__":
    main()
