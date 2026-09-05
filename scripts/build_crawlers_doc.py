"""Rewrite the tables in docs/CRAWLERS.md from the agent list.

The page has said "generated from agents.json" since the first release and
nothing generated it, so the list grew and the page stayed where it was. This is
the missing half. It touches only the count line and the table under each bucket
heading; the prose around them stays hand written, because prose is the part a
person should be writing.

    python scripts/build_crawlers_doc.py          rewrite the page
    python scripts/build_crawlers_doc.py --check  say whether it is current

tests/test_crawlers_doc.py enforces the result, so a contributor who edits
agents.json and forgets this script gets a failing test rather than a page that
quietly disagrees with the tool.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "src" / "geo_check" / "data" / "agents.json"
DOC = ROOT / "docs" / "CRAWLERS.md"

BUCKETS = [
    ("citation", "## Citation crawlers", "worth 50 points"),
    ("user_fetch", "## User fetch crawlers", "worth 20 points"),
    ("training", "## Training crawlers", "worth zero points"),
]
WORTH = {bucket: worth for bucket, _, worth in BUCKETS}

HEADER = "| Agent | Vendor | Obeys robots.txt | What it does |\n| --- | --- | --- | --- |"


def first_sentence(note: str) -> str:
    """The table gets the headline, the JSON keeps the reasoning."""
    return re.split(r"(?<=[a-z0-9)])\. ", note.strip(), maxsplit=1)[0].rstrip(".")


def row(agent: dict) -> str:
    docs = agent.get("docs")
    # An entry with no vendor documentation gets no link, rather than a link to
    # something that is not documentation.
    vendor = f"[{agent['vendor']}]({docs})" if docs else agent["vendor"]
    note = first_sentence(agent.get("note", ""))
    return f"| `{agent['token']}` | {vendor} | {agent['obeys_robots']} | {note} |"


def table(agents: list[dict], bucket: str) -> str:
    rows = sorted(
        (a for a in agents if a["bucket"] == bucket),
        key=lambda a: a["token"].lower(),
    )
    count = f"{len(rows)} agents, {WORTH[bucket]}."
    return "\n".join([count, "", HEADER, *map(row, rows)])


def rebuild(body: str, agents: list[dict], reviewed: str) -> str:
    for bucket, heading, _ in BUCKETS:
        start = body.index(heading) + len(heading)
        end = body.find("\n## ", start)
        end = end if end != -1 else len(body)
        body = body[:start] + "\n\n" + table(agents, bucket) + "\n" + body[end:]
    return re.sub(r"Last reviewed \d{4}-\d{2}-\d{2}", f"Last reviewed {reviewed}", body)


def main() -> int:
    parser = argparse.ArgumentParser(description="Rewrite docs/CRAWLERS.md from agents.json.")
    parser.add_argument("--check", action="store_true", help="Exit 1 if the page is out of date.")
    args = parser.parse_args()

    data = json.loads(AGENTS.read_text(encoding="utf-8"))
    current = DOC.read_text(encoding="utf-8")
    wanted = rebuild(current, data["agents"], data["last_reviewed"])

    if args.check:
        if current == wanted:
            print("docs/CRAWLERS.md is current.")
            return 0
        print("docs/CRAWLERS.md is behind agents.json. Run scripts/build_crawlers_doc.py.")
        return 1

    DOC.write_text(wanted, encoding="utf-8", newline="\n")
    counts = ", ".join(
        f"{sum(1 for a in data['agents'] if a['bucket'] == b)} {b}" for b, _, _ in BUCKETS
    )
    print(f"docs/CRAWLERS.md rewritten: {counts}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
