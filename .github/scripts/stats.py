"""Build contribution stats cards (light + dark SVG) from the GitHub GraphQL API.

Counts the same contributions GitHub shows on the public profile calendar.
Usage: GITHUB_TOKEN=... python stats.py <user> <out_dir>
"""
import json
import os
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone

USER = sys.argv[1]
OUT = sys.argv[2]
TOKEN = os.environ["GITHUB_TOKEN"]


def gql(query, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "User-Agent": "profile-stats"},
    )
    with urllib.request.urlopen(req) as r:
        body = json.load(r)
    if "errors" in body:
        raise SystemExit(body["errors"])
    return body["data"]


created = gql("query($u:String!){user(login:$u){createdAt}}", {"u": USER})["user"]["createdAt"]
start = datetime.fromisoformat(created.replace("Z", "+00:00")).date()
today = datetime.now(timezone.utc).date()

CAL = """query($u:String!,$f:DateTime!,$t:DateTime!){user(login:$u){contributionsCollection(from:$f,to:$t){
contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}"""

days = {}
cur = start
while cur <= today:
    end = min(cur + timedelta(days=364), today)
    data = gql(CAL, {"u": USER, "f": f"{cur}T00:00:00Z", "t": f"{end}T23:59:59Z"})
    for w in data["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]:
        for d in w["contributionDays"]:
            days[date.fromisoformat(d["date"])] = d["contributionCount"]
    cur = end + timedelta(days=1)

ordered = sorted(days)
year_ago = today - timedelta(days=365)
last_year = sum(c for d, c in days.items() if d > year_ago)
active_year = sum(1 for d, c in days.items() if d > year_ago and c > 0)
all_time = sum(days.values())

longest = run = 0
for d in ordered:
    run = run + 1 if days[d] > 0 else 0
    longest = max(longest, run)

# Current streak: today may still be empty without breaking it.
current = 0
d = today if days.get(today, 0) > 0 else today - timedelta(days=1)
while days.get(d, 0) > 0:
    current += 1
    d -= timedelta(days=1)

stats = [
    (f"{last_year:,}", "Contributions", "last 365 days"),
    (f"{active_year}", "Active days", "last 365 days"),
    (f"{current}", "Current streak", "days"),
    (f"{longest}", "Longest streak", "days"),
]

THEMES = {
    "light": dict(bg="#ffffff", border="#d0d7de", value="#0969da", label="#1f2328", sub="#656d76"),
    "dark": dict(bg="#0d1117", border="#30363d", value="#7aa2f7", label="#e6edf3", sub="#8b949e"),
}


def card(t):
    w, h, col = 880, 150, 220
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
        f'<rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="10" fill="{t["bg"]}" stroke="{t["border"]}"/>',
        '<style>text{font-family:"Segoe UI",Ubuntu,Helvetica,Arial,sans-serif;text-anchor:middle}</style>',
    ]
    for i, (value, label, sub) in enumerate(stats):
        x = col * i + col / 2
        if i:
            parts.append(f'<line x1="{col*i}" y1="28" x2="{col*i}" y2="{h-28}" stroke="{t["border"]}"/>')
        parts += [
            f'<text x="{x}" y="66" font-size="34" font-weight="700" fill="{t["value"]}">{value}</text>',
            f'<text x="{x}" y="96" font-size="15" font-weight="600" fill="{t["label"]}">{label}</text>',
            f'<text x="{x}" y="116" font-size="12" fill="{t["sub"]}">{sub}</text>',
        ]
    parts.append(
        f'<text x="{w-14}" y="{h-10}" font-size="10" fill="{t["sub"]}" style="text-anchor:end">'
        f'updated {datetime.now(timezone.utc):%d %b %Y %H:%M} UTC · {all_time:,} all-time</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts)


os.makedirs(OUT, exist_ok=True)
for name, theme in THEMES.items():
    suffix = "" if name == "light" else "-dark"
    with open(os.path.join(OUT, f"stats{suffix}.svg"), "w", encoding="utf-8") as f:
        f.write(card(theme))
print(stats, "all-time", all_time)
