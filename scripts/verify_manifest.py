"""Check rows of data/corpus_manifest.csv against the live web.

The manifest claims a SHA-256 for each robots.txt recorded during the study.
This fetches those files now and reports match, changed or unreachable. It
hashes exactly the way the recording did, so a mismatch means the site changed
rather than the reader normalising differently.

    python scripts/verify_manifest.py --sample 5
    python scripts/verify_manifest.py wikipedia.org bbc.co.uk

A changed hash is not a failure of the study. Sites edit robots.txt, and the
manifest carries the timestamp of every read for that reason. What the manifest
rules out is a number that was never measured at all.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from geo_check import fetch as fetcher

MANIFEST = ROOT / "data" / "corpus_manifest.csv"


def hashed_rows() -> list[dict[str, str]]:
    with MANIFEST.open(encoding="utf-8") as handle:
        return [row for row in csv.DictReader(handle) if row["robots_sha256"]]


def pick(rows: list[dict[str, str]], names: list[str], sample: int) -> list[dict[str, str]]:
    if names:
        wanted = set(names)
        chosen = [row for row in rows if row["domain"] in wanted]
        unknown = wanted - {row["domain"] for row in chosen}
        if unknown:
            print(f"not in the manifest with a hash: {sorted(unknown)}", file=sys.stderr)
        return chosen
    # Ordered by sha256 of the domain, so "pick some" is reproducible and cannot
    # be quietly steered towards the rows that happen to still match.
    return sorted(rows, key=lambda row: hashlib.sha256(row["domain"].encode()).hexdigest())[:sample]


def check(row: dict[str, str], client) -> str:
    result = fetcher.fetch(row["robots_url"], client=client)
    if result.status != 200:
        return f"UNREACHABLE  {row['domain']}  ({result.status or result.error})"
    live = hashlib.sha256((result.text or "").encode("utf-8")).hexdigest()
    if live == row["robots_sha256"]:
        return f"MATCH        {row['domain']}  {live[:16]}"
    return (
        f"CHANGED      {row['domain']}  recorded {row['robots_sha256'][:16]} "
        f"on {row['fetched_at'][:10]}, live {live[:16]}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "domains", nargs="*", help="domains to check, default a reproducible sample"
    )
    parser.add_argument(
        "--sample", type=int, default=5, help="how many to check when none are named"
    )
    args = parser.parse_args()

    rows = pick(hashed_rows(), args.domains, args.sample)
    if not rows:
        print("nothing to check", file=sys.stderr)
        return 1

    tally: dict[str, int] = {}
    with fetcher.new_client() as client:
        for row in rows:
            line = check(row, client)
            tally[line.split()[0]] = tally.get(line.split()[0], 0) + 1
            print(line)
    print("  ".join(f"{name.lower()} {count}" for name, count in sorted(tally.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
