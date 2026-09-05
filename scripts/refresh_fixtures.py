"""Refresh the offline test fixtures from the live web.

Run this deliberately, never as part of the test suite. Tests must run offline,
in seconds, against saved files. Hitting 500 real sites on every code change is
slow, flaky and rude.

    python scripts/refresh_fixtures.py                  # the whole corpus
    python scripts/refresh_fixtures.py --limit 20       # a slice, for a smoke run
    python scripts/refresh_fixtures.py --only sapo.pt observador.pt

Saves per domain: the homepage, robots.txt, llms.txt, the sitemap and every
sampled page, with the fetch date, so stale fixtures are visible.
"""

from __future__ import annotations

import argparse
import json
import time
from concurrent import futures
from datetime import datetime, timezone
from pathlib import Path

from geo_check.fetch import fetch as live_fetch
from geo_check.fetch import new_client
from geo_check.fixtures import Recorder, save
from geo_check.site import SiteUnavailable, build_site

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data" / "corpus.txt"
FIXTURES = ROOT / "tests" / "fixtures"


def read_corpus(path: Path) -> list[str]:
    lines = (
        line.split("#", 1)[0].strip() for line in path.read_text(encoding="utf-8").splitlines()
    )
    return [line for line in lines if line]


def record(domain: str, pages: int, directory: Path, delay: float = 0.0) -> tuple[str, str, int]:
    """Fetch one domain and write its fixture. Never raises."""
    if delay:
        time.sleep(delay)
    client = new_client()
    recorder = Recorder(lambda url: live_fetch(url, client))
    try:
        try:
            build_site(domain, pages=pages, fetcher=recorder)
            outcome = "scored"
        except SiteUnavailable as exc:
            outcome = "aborted: " + exc.reason
        except Exception as exc:  # noqa: BLE001 - a crash here is the finding
            outcome = "crashed: " + type(exc).__name__ + ": " + str(exc)
    finally:
        client.close()
    target = save(directory, domain, recorder.responses, outcome)
    return domain, outcome, target.stat().st_size


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Record live responses as offline fixtures.")
    parser.add_argument("--limit", type=int, help="Record only the first N domains of the corpus.")
    parser.add_argument("--only", nargs="+", help="Record only these domains.")
    parser.add_argument("--pages", type=int, default=5, help="Pages to sample per site. Default 5.")
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help=(
            "Domains in flight. Default 4. Eight was enough to get every Shopify"
            " storefront in a batch challenged by Cloudflare at once, which does"
            " not measure the sites, it measures the sweep."
        ),
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Seconds to wait before starting each domain. Default 1.",
    )
    parser.add_argument("--out", default=str(FIXTURES), help="Where to write the fixtures.")
    parser.add_argument(
        "--report",
        help=(
            "Write the per domain outcome to this path. This is the robustness"
            " evidence and it is small enough to commit, unlike the fixtures."
        ),
    )
    args = parser.parse_args(argv)

    domains = args.only or read_corpus(CORPUS)
    if args.limit:
        domains = domains[: args.limit]
    directory = Path(args.out)

    print(f"recording {len(domains)} domains into {directory}")
    counts: dict[str, int] = {}
    outcomes: dict[str, str] = {}
    total_bytes = 0
    with futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        jobs = [
            pool.submit(record, domain, args.pages, directory, args.delay * (index % args.workers))
            for index, domain in enumerate(domains)
        ]
        for index, job in enumerate(futures.as_completed(jobs), start=1):
            domain, outcome, size = job.result()
            total_bytes += size
            outcomes[domain] = outcome
            counts[outcome.split(":")[0]] = counts.get(outcome.split(":")[0], 0) + 1
            print(f"  [{index:>3}/{len(domains)}] {size / 1024:>7.0f} KB  {domain:32} {outcome}")

    print()
    for outcome, count in sorted(counts.items()):
        share = 100 * count / len(domains)
        print(f"{outcome:10} {count:>3}  ({share:.0f}%)")
    print(f"{'total':10} {total_bytes / 1024 / 1024:.1f} MB on disk")

    if args.report:
        completed = counts.get("scored", 0)
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "domains": len(domains),
            "completed": completed,
            "completed_share": round(100 * completed / len(domains), 1),
            "by_outcome": dict(sorted(counts.items())),
            "note": (
                "A run that aborts with a logged reason counts as the tool working."
                " An aborted domain is almost always a 401, 403 or 202 challenge from"
                " a CDN or bot manager, which refuses a browser the same way. It must"
                " not be read as that site blocking AI crawlers."
            ),
            "results": dict(sorted(outcomes.items())),
        }
        Path(args.report).write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print("report written to " + args.report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
