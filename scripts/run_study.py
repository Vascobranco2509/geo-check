"""Run the audit across the corpus and aggregate the numbers.

This produces the launch study, not just a test report. The headline number is
how many sites block the crawlers that feed AI answers while believing they
only opted out of training.

Reads the recorded fixtures, so it is offline and reproducible. Record them
first with scripts/refresh_fixtures.py.

    python scripts/run_study.py --out data/study.json
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from geo_check.checks import run_all
from geo_check.cli import collect_caps
from geo_check.fixtures import Replayer, available, load
from geo_check.models import Bucket, Category
from geo_check.robots import bucket_counts
from geo_check.scoring import score_category, training_posture
from geo_check.site import SiteUnavailable, build_site

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data" / "corpus_500.txt"
CATEGORIES = ROOT / "data" / "corpus_categories.csv"
FIXTURES = ROOT / "tests" / "fixtures" / "corpus"

# The crawlers that exist only to feed AI answers. Googlebot and Bingbot also
# carry classic search, so blocking those is a bigger and different story.
AI_ONLY = ("OAI-SearchBot", "Claude-SearchBot", "PerplexityBot")

# Publishing platform is a property of a site, not a category. Making it a
# category produced an artifact: forty domains read out of a Shopify directory
# came back 100 percent Shopify with 100 percent llms.txt adoption, which is what
# the platform ships rather than what small businesses do. Detected for all 500
# and reported as a dimension that cuts across every category.
# The generator meta tag is the reliable signal, so it is read first. Asset
# paths are the fallback and they need care: matching the bare word prestashop
# labelled klaviyo.com, an email SaaS, as a shop, because its marketing pages
# name every platform it integrates with.
GENERATOR_NAMES = (
    "wordpress",
    "shopify",
    "wix",
    "squarespace",
    "webflow",
    "prestashop",
    "magento",
    "drupal",
    "joomla",
    "hubspot",
    "ghost",
    "gatsby",
    "hugo",
    "jekyll",
)
PLATFORM_SIGNS = (
    ("WordPress", (r"/wp-content/", r"/wp-includes/", r"/wp-json/")),
    ("Shopify", (r"cdn\.shopify\.com", r"Shopify\.theme", r"shopifycdn\.")),
    ("Wix", (r"static\.wixstatic\.com", r"wixsite\.com")),
    ("Squarespace", (r"static1\.squarespace\.com", r"squarespace-cdn")),
    ("Webflow", (r"assets\.website-files\.com", r"uploads-ssl\.webflow")),
    ("PrestaShop", (r"var\s+prestashop\s*=", r"/modules/ps_")),
    ("Magento", (r"/static/version\d", r"Magento_[A-Z]")),
    ("Drupal", (r"/sites/default/files/", r"Drupal\.settings")),
    ("Next.js", (r"__NEXT_DATA__", r"/_next/static/")),
)


def detect_platform(site) -> str:
    """What published this page.

    The generator meta tag decides when a page declares one, because that is the
    site saying so rather than us guessing. Otherwise the first asset pattern
    that matches wins, WordPress before Shopify, since a WooCommerce store
    sometimes loads a Shopify script and never the other way round.
    """
    if not site.pages:
        return "unknown"
    page = site.pages[0]

    for meta in page.soup.find_all("meta"):
        if (meta.get("name") or "").strip().lower() != "generator":
            continue
        declared = (meta.get("content") or "").strip().lower()
        for known in GENERATOR_NAMES:
            if known in declared:
                return known.capitalize() if known != "wordpress" else "WordPress"

    blob = page.html[:200000] + " " + " ".join(page.headers.values())
    for name, patterns in PLATFORM_SIGNS:
        if any(re.search(pattern, blob, re.IGNORECASE) for pattern in patterns):
            return name
    return "custom or unidentified"


def read_categories(path: Path) -> dict[str, str]:
    """Domain to site type, from data/corpus_categories.csv.

    Categories used to live in section comments inside the corpus file. They do
    not any more: a section boundary orders the domains, and an ordering is a
    fact about the corpus that the file has no business stating. Reading a
    separate table also fails loudly when it goes stale, which the comment
    parsing did not.
    """
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    categories = {row["domain"]: row["category"] for row in rows}
    if not categories:
        raise SystemExit(f"no categories in {path}")
    return categories


def measure(domain: str) -> dict:
    """One site, reduced to the facts the study rests on."""
    try:
        site = build_site(domain, pages=5, fetcher=Replayer(load(FIXTURES, domain)["responses"]))
    except SiteUnavailable as exc:
        return {"domain": domain, "outcome": "aborted", "reason": exc.reason}

    results = run_all(site)
    access = score_category(results, Category.ACCESS, caps=collect_caps(site))
    readability = score_category(results, Category.READABILITY)
    by_token = {v.token: v for v in site.agent_verdicts}
    citation_allowed, citation_total = bucket_counts(site.agent_verdicts, Bucket.CITATION)
    fetch_allowed, fetch_total = bucket_counts(site.agent_verdicts, Bucket.USER_FETCH)
    training_allowed, training_total = bucket_counts(site.agent_verdicts, Bucket.TRAINING)
    ai_only_blocked = [t for t in AI_ONLY if t in by_token and not by_token[t].allowed]
    classic_open = all(by_token[t].allowed for t in ("Googlebot", "Bingbot") if t in by_token)
    checks = {r.check_id: r for r in results}

    return {
        "domain": domain,
        "outcome": "scored",
        "access": round(access.final_score, 2),
        "access_letter": access.letter,
        "readability": round(readability.final_score, 2),
        "readability_letter": readability.letter,
        "citation_allowed": citation_allowed,
        "citation_total": citation_total,
        "user_fetch_allowed": fetch_allowed,
        "user_fetch_total": fetch_total,
        "training_posture": training_posture(training_allowed, training_total),
        "ai_only_blocked": ai_only_blocked,
        # The failure this project exists to find: every crawler that only feeds
        # AI answers is shut out, while Google and Bing still get through.
        "ai_blackout": len(ai_only_blocked) == len(AI_ONLY) and classic_open,
        "blocks_oai_searchbot": "OAI-SearchBot" in ai_only_blocked,
        "blocks_gptbot": "GPTBot" in by_token and not by_token["GPTBot"].allowed,
        "robots_is_real": site.robots_is_real,
        "llms_txt": bool((site.llms_txt or "").strip()),
        "sitemap": site.sitemap_url is not None,
        "jsonld": checks["jsonld_valid"].ratio if "jsonld_valid" in checks else 0.0,
        "raw_html": checks["raw_html_content"].ratio if "raw_html_content" in checks else 0.0,
        "pages_sampled": len(site.pages),
        "platform": detect_platform(site),
    }


def share(count: int, total: int) -> float:
    return round(100 * count / total, 1) if total else 0.0


def summarise(rows: list[dict], categories: dict[str, str]) -> dict:
    scored = [r for r in rows if r["outcome"] == "scored"]
    aborted = [r for r in rows if r["outcome"] == "aborted"]

    def group(key):
        buckets = defaultdict(list)
        for row in scored:
            buckets[key(row)].append(row)
        return buckets

    by_category = defaultdict(list)
    for row in rows:
        by_category[categories.get(row["domain"], "unknown")].append(row)

    category_summary = {}
    for name, group_rows in sorted(by_category.items()):
        group_scored = [r for r in group_rows if r["outcome"] == "scored"]
        category_summary[name] = {
            "domains": len(group_rows),
            "scored": len(group_scored),
            "aborted": len(group_rows) - len(group_scored),
            "abort_share": share(len(group_rows) - len(group_scored), len(group_rows)),
            "blocks_any_ai_only": share(
                sum(1 for r in group_scored if r["ai_only_blocked"]), len(group_scored)
            ),
            "ai_blackout": share(
                sum(1 for r in group_scored if r["ai_blackout"]), len(group_scored)
            ),
            "median_access": (
                sorted(r["access"] for r in group_scored)[len(group_scored) // 2]
                if group_scored
                else None
            ),
            "median_readability": (
                sorted(r["readability"] for r in group_scored)[len(group_scored) // 2]
                if group_scored
                else None
            ),
        }

    blocks_any = [r for r in scored if r["ai_only_blocked"]]
    blackout = [r for r in scored if r["ai_blackout"]]
    training_only = [r for r in scored if r["blocks_gptbot"] and not r["blocks_oai_searchbot"]]
    both = [r for r in scored if r["blocks_gptbot"] and r["blocks_oai_searchbot"]]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "corpus": len(rows),
        "scored": len(scored),
        "aborted": len(aborted),
        "abort_reasons": dict(Counter(r["reason"].split(":")[0] for r in aborted).most_common()),
        "headline": {
            "blocks_at_least_one_ai_only_crawler": {
                "count": len(blocks_any),
                "share": share(len(blocks_any), len(scored)),
            },
            "ai_blackout": {
                "count": len(blackout),
                "share": share(len(blackout), len(scored)),
                "meaning": (
                    "Every crawler that exists only to feed AI answers is blocked,"
                    " while Google and Bing still get through. Reachable by classic"
                    " search, invisible to ChatGPT, Claude and Perplexity."
                ),
            },
            "blocked_training_only": {
                "count": len(training_only),
                "share": share(len(training_only), len(scored)),
                "meaning": "Opted out of training and kept AI search. The correct configuration.",
            },
            "blocked_training_and_search": {
                "count": len(both),
                "share": share(len(both), len(scored)),
                "meaning": "Blocked GPTBot and OAI-SearchBot. Often the same intention, twice the cost.",
            },
        },
        "scores": {
            "access_median": sorted(r["access"] for r in scored)[len(scored) // 2],
            "readability_median": sorted(r["readability"] for r in scored)[len(scored) // 2],
            "access_grades": dict(Counter(r["access_letter"] for r in scored).most_common()),
            "readability_grades": dict(
                Counter(r["readability_letter"] for r in scored).most_common()
            ),
        },
        "adoption": {
            "llms_txt": share(sum(1 for r in scored if r["llms_txt"]), len(scored)),
            "sitemap": share(sum(1 for r in scored if r["sitemap"]), len(scored)),
            "no_robots_txt": share(sum(1 for r in scored if not r["robots_is_real"]), len(scored)),
            "jsonld_on_every_page": share(
                sum(1 for r in scored if r["jsonld"] == 1.0), len(scored)
            ),
            "content_in_raw_html": share(
                sum(1 for r in scored if r["raw_html"] == 1.0), len(scored)
            ),
        },
        "training_posture": dict(Counter(r["training_posture"] for r in scored).most_common()),
        "by_category": category_summary,
        "by_platform": {
            name: {
                "sites": len(group),
                "median_access": sorted(r["access"] for r in group)[len(group) // 2],
                "median_readability": sorted(r["readability"] for r in group)[len(group) // 2],
                "blocks_any_ai_only": share(
                    sum(1 for r in group if r["ai_only_blocked"]), len(group)
                ),
                "llms_txt": share(sum(1 for r in group if r["llms_txt"]), len(group)),
                "content_in_raw_html": share(
                    sum(1 for r in group if r["raw_html"] == 1.0), len(group)
                ),
            }
            for name, group in sorted(
                group(lambda r: r["platform"]).items(), key=lambda kv: -len(kv[1])
            )
        },
        "sites": sorted(rows, key=lambda r: r["domain"]),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Aggregate the corpus into the launch study.")
    parser.add_argument("--out", default=str(ROOT / "data" / "study.json"))
    parser.add_argument(
        "--robustness",
        help=(
            "Also write the per domain outcome here. Derived from the fixtures"
            " rather than from the recording run, so it is reproducible offline."
            " No default on purpose: data/robustness_report.json is committed,"
            " and reproducing the work should not quietly modify it."
        ),
    )
    args = parser.parse_args(argv)

    categories = read_categories(CATEGORIES)
    on_disk = set(available(FIXTURES))
    # The corpus decides what is in the study, not whatever is left on disk from
    # an older version of it.
    recorded = [d for d in categories if d in on_disk]
    if not recorded:
        print("no fixtures for the current corpus. run scripts/refresh_fixtures.py first.")
        return 1
    stale = len(on_disk) - len(recorded)
    if stale:
        print(f"ignoring {stale} fixtures for domains no longer in the corpus")

    rows = [measure(domain) for domain in recorded]
    study = summarise(rows, categories)
    Path(args.out).write_text(
        json.dumps(study, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    head = study["headline"]
    print(f"corpus {study['corpus']}, scored {study['scored']}, aborted {study['aborted']}\n")
    for key, entry in head.items():
        print(f"  {entry['share']:>5.1f}%  {entry['count']:>3}  {key}")
    print(
        f"\n  median Access {study['scores']['access_median']}, "
        f"median Readability {study['scores']['readability_median']}"
    )
    print("  written to " + args.out)

    if args.robustness:
        outcomes = {
            r["domain"]: ("scored" if r["outcome"] == "scored" else "aborted: " + r["reason"])
            for r in rows
        }
        completed = sum(1 for value in outcomes.values() if value == "scored")
        report = {
            "generated_at": study["generated_at"],
            "domains": len(outcomes),
            "completed": completed,
            "completed_share": round(100 * completed / len(outcomes), 1),
            "by_outcome": {"scored": completed, "aborted": len(outcomes) - completed},
            "note": (
                "A run that aborts with a logged reason counts as the tool working."
                " An aborted domain is almost always a 401, 403 or 202 challenge"
                " from a CDN or bot manager, which refuses a browser the same way."
                " It must not be read as that site blocking AI crawlers."
            ),
            "results": dict(sorted(outcomes.items())),
        }
        Path(args.robustness).write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + chr(10), encoding="utf-8"
        )
        print("  robustness written to " + args.robustness)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
