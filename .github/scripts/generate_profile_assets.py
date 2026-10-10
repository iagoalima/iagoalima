#!/usr/bin/env python3
"""Generate local SVG assets for the iagoalima GitHub profile README."""
from datetime import date, timedelta
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen
import json
import re
import xml.sax.saxutils as xml

USER = "iagoalima"
OUT = Path("assets/profile")
OUT.mkdir(parents=True, exist_ok=True)

def get(url, accept="application/vnd.github+json"):
    req = Request(url, headers={"User-Agent": "profile-assets-generator", "Accept": accept})
    with urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8")

def esc(value):
    return xml.escape(str(value), {'"': "&quot;"})

# Pull contribution-calendar cells directly from GitHub's public profile page.
today = date.today()
start = today - timedelta(days=370)
calendar_url = f"https://github.com/users/{USER}/contributions?from={start.isoformat()}&to={today.isoformat()}"
calendar_html = get(calendar_url, "text/html")
cells = []
# GitHub has used both <rect> and <td> elements for contribution calendar cells.
# Parse any HTML tag carrying data-date, rather than assuming a specific element type.
for tag in re.findall(r"<[^>]+>", calendar_html):
    date_match = re.search(r'data-date=["\\'](\\d{4}-\\d{2}-\\d{2})["\\']', tag)
    count_match = re.search(r'data-count=["\\'](\\d+)["\\']', tag)
    level_match = re.search(r'data-level=["\\'](\\d+)["\\']', tag)
    if date_match and (count_match or level_match):
        try:
            # Exact counts are used when available; otherwise use the 0–4 activity level.
            value = int(count_match.group(1)) if count_match else int(level_match.group(1))
            cells.append((date.fromisoformat(date_match.group(1)), value))
        except ValueError:
            pass

if not cells:
    raise RuntimeError("Could not parse contribution calendar from GitHub's public profile page.")

cells = sorted({d: n for d, n in cells}.items())
# Keep only the latest 53 weeks, padding the start to a Sunday.
first_day = today - timedelta(days=370)
first_day -= timedelta(days=(first_day.weekday() + 1) % 7)
contrib = {d: n for d, n in cells}
weeks = []
cursor = first_day
while cursor <= today:
    week = []
    for _ in range(7):
        week.append((cursor, contrib.get(cursor, 0)))
        cursor += timedelta(days=1)
    weeks.append(week)
weeks = weeks[-53:]

def level(n):
    # The public calendar's data-level is 0–4; data-count, when available, is an exact count.
    if n <= 0: return "#161b22"
    if n <= 1: return "#0e4429"
    if n <= 2: return "#006d32"
    if n <= 3: return "#26a641"
    return "#39d353"

width, height = 850, 184
parts = [
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
    '<rect width="100%" height="100%" rx="12" fill="#0d1117"/>',
    '<text x="24" y="30" fill="#c9d1d9" font-family="Segoe UI,Arial,sans-serif" font-size="16" font-weight="600">Contribution activity</text>',
    f'<text x="{width-24}" y="30" text-anchor="end" fill="#8b949e" font-family="Segoe UI,Arial,sans-serif" font-size="11">Last 12 months · GitHub contribution calendar</text>',
]
# Day labels and month labels
for label, row in [("Mon", 1), ("Wed", 3), ("Fri", 5)]:
    y = 50 + row * 16
    parts.append(f'<text x="24" y="{y+9}" fill="#8b949e" font-family="Segoe UI,Arial,sans-serif" font-size="10">{label}</text>')
x0, y0, step, cell = 58, 48, 14, 10
last_month = None
for wi, week in enumerate(weeks):
    for day, n in week:
        row = day.weekday()
        x, y = x0 + wi * step, y0 + row * 16
        parts.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{level(n)}"><title>{esc(day.isoformat())}: {n} contributions</title></rect>')
        if day.day <= 7 and day.month != last_month:
            parts.append(f'<text x="{x}" y="43" fill="#8b949e" font-family="Segoe UI,Arial,sans-serif" font-size="10">{day.strftime("%b")}</text>')
            last_month = day.month
parts.extend([
    '<text x="58" y="174" fill="#8b949e" font-family="Segoe UI,Arial,sans-serif" font-size="10">Less</text>',
])
for i, color in enumerate(["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]):
    parts.append(f'<rect x="{94+i*14}" y="165" width="10" height="10" rx="2" fill="{color}"/>')
parts.append('<text x="174" y="174" fill="#8b949e" font-family="Segoe UI,Arial,sans-serif" font-size="10">More</text>')
parts.append('</svg>')
(OUT / "activity.svg").write_text("\n".join(parts), encoding="utf-8")

# Use public REST data to create a self-hosted achievements panel.
user = json.loads(get(f"https://api.github.com/users/{USER}"))
repos = []
page = 1
while page <= 10:
    batch = json.loads(get(f"https://api.github.com/users/{USER}/repos?per_page=100&sort=updated&page={page}"))
    if not batch:
        break
    repos.extend(batch)
    if len(batch) < 100:
        break
    page += 1
public_repos = int(user.get("public_repos", len(repos)))
stars = sum(int(repo.get("stargazers_count", 0)) for repo in repos)
forks = sum(int(repo.get("forks_count", 0)) for repo in repos)
followers = int(user.get("followers", 0))
contributions_year = sum(1 for d, n in cells if d.year == today.year and n > 0)
metrics = [
    ("PUBLIC REPOSITORIES", public_repos, "Projects shared publicly"),
    ("STARS EARNED", stars, "Stars across public repositories"),
    ("FOLLOWERS", followers, "GitHub community"),
    ("ACTIVE DAYS THIS YEAR", contributions_year, "Days with GitHub activity"),
]
card_w, card_h, gap = 190, 108, 14
panel_w, panel_h = 4*card_w + 3*gap + 40, 180
trophy = [
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{panel_w}" height="{panel_h}" viewBox="0 0 {panel_w} {panel_h}">',
    '<rect width="100%" height="100%" rx="12" fill="#0d1117"/>',
    '<text x="20" y="28" fill="#c9d1d9" font-family="Segoe UI,Arial,sans-serif" font-size="16" font-weight="600">Profile milestones</text>',
]
for i, (label, value, detail) in enumerate(metrics):
    x, y = 20 + i*(card_w+gap), 44
    trophy.append(f'<rect x="{x}" y="{y}" width="{card_w}" height="{card_h}" rx="9" fill="#111827" stroke="#1f3b63"/>')
    trophy.append(f'<rect x="{x}" y="{y}" width="4" height="{card_h}" rx="2" fill="#4d9fff"/>')
    trophy.append(f'<text x="{x+14}" y="{y+25}" fill="#8b949e" font-family="Segoe UI,Arial,sans-serif" font-size="10" font-weight="600">{esc(label)}</text>')
    trophy.append(f'<text x="{x+14}" y="{y+60}" fill="#4d9fff" font-family="Segoe UI,Arial,sans-serif" font-size="27" font-weight="700">{esc(value)}</text>')
    trophy.append(f'<text x="{x+14}" y="{y+83}" fill="#c9d1d9" font-family="Segoe UI,Arial,sans-serif" font-size="10">{esc(detail)}</text>')
trophy.append('</svg>')
(OUT / "achievements.svg").write_text("\n".join(trophy), encoding="utf-8")
print("Generated assets/profile/activity.svg and assets/profile/achievements.svg")
