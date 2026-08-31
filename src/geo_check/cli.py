"""Command line entry point.

    geo-check example.com
    geo-check example.com --pages 10 --json report.json --output report.md

Everything printed here is rendered from the JSON payload, not from the check
results, so the terminal, the JSON file and the markdown report can never
disagree about the same run.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .checks import run_all
from .models import Bucket, Category
from .report.json_out import build
from .report.markdown import render as render_markdown
from .robots import bucket_counts, is_blanket_disallow
from .scoring import CAP_ALL_CITATION_BLOCKED, CAP_BLANKET_DISALLOW, score_category
from .site import SiteUnavailable, build_site

EXIT_OK = 0
EXIT_ABORTED = 2
RULE = "-" * 72

GENERIC_ABORT_NOTE = "No score produced. A site that does not answer has nothing honest to score."
# A homepage that refuses this tool refuses AI crawlers the same way. That is
# blocking above robots.txt, which this tool does not otherwise see, so the one
# place it does surface is here.
WAF_ABORT_NOTE = (
    "No score produced. A 401 or 403 on the homepage is a block above robots.txt,"
    " at the CDN, WAF or bot manager. Whatever robots.txt says, an AI crawler"
    " arriving from a data centre hits the same wall. Verify from the server"
    " logs or the CDN dashboard, because this tool cannot see that layer."
)
ABORT_NOTE = {401: WAF_ABORT_NOTE, 403: WAF_ABORT_NOTE}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="geo-check",
        description="Check whether a website is reachable and readable by AI crawlers.",
    )
    parser.add_argument("domain", help="Domain or URL to audit, for example example.com")
    parser.add_argument(
        "--pages",
        type=int,
        default=5,
        help="How many pages to sample, the homepage included. Default 5.",
    )
    parser.add_argument("--json", dest="json_path", help="Write the JSON result to this path.")
    parser.add_argument("--output", dest="md_path", help="Write the markdown report to this path.")
    return parser


def status_in(reason: str) -> int | None:
    """Pull the HTTP status back out of an abort reason, when there is one."""
    for token in reason.split():
        if token.isdigit():
            return int(token)
    return None


def collect_caps(site) -> list[tuple[int, str]]:
    """The critical failures that cap the Access score.

    A blanket `Disallow: /` only caps at 10 when it actually shuts everyone out.
    Cloudflare style files block `*` and then name the crawlers they welcome,
    and treating those as a total block would be wrong.
    """
    allowed, total = bucket_counts(site.agent_verdicts, Bucket.CITATION)
    if not total or allowed:
        return []

    caps = [(CAP_ALL_CITATION_BLOCKED, "all citation crawlers blocked")]
    if site.robots_txt and is_blanket_disallow(site.robots_txt):
        caps.append((CAP_BLANKET_DISALLOW, "User-agent: * with Disallow: /"))
    return caps


def _bucket_block(payload: dict, bucket: str, heading: str) -> list[str]:
    data = payload["crawlers"][bucket]
    allowed = [a["token"] for a in data["agents"] if a["allowed"]]
    blocked = [a for a in data["agents"] if not a["allowed"]]
    lines = [
        heading + "   " + str(data["allowed"]) + " of " + str(data["total"]) + " allowed",
        "  allowed  " + (", ".join(allowed) if allowed else "none"),
    ]
    if blocked:
        lines.append("  blocked  " + ", ".join(a["token"] for a in blocked))
        for rule in sorted({a["matched_rule"] for a in blocked if a["matched_rule"]}):
            lines.append("           because of  " + rule)
    lines.append("")
    return lines


def _actions_block(payload: dict) -> list[str]:
    failed = [c for c in payload["checks"] if c["fix"] and c["ratio"] < 1.0]
    if not failed:
        return [RULE, "WHAT TO CHANGE", "  Nothing. Every check passed.", ""]

    lines = [RULE, "WHAT TO CHANGE FIRST", ""]
    additions = payload.get("robots_txt_additions", "")
    if additions:
        lines.append("  Add these lines to " + payload["robots"]["url"] + ":")
        lines.append("")
        lines += ["      " + line for line in additions.splitlines()]
        lines.append("")

    ordered = sorted(failed, key=lambda c: c["weight"] * (1 - c["ratio"]), reverse=True)
    for check in ordered[:5]:
        cost = round(check["weight"] * (1 - check["ratio"]), 1)
        lines.append("  " + format(cost, "g") + " points  " + check["title"])
        lines.append("            " + check["fix"]["summary"])
    lines.append("")
    return lines


def render_text(payload: dict) -> str:
    run = payload["run"]
    scores = payload["scores"]
    posture = payload["training_posture"]
    out: list[str] = []
    add = out.append

    add(payload["tool"]["name"] + " " + payload["tool"]["version"] + "   " + run["domain"])
    pages = run["pages_sampled"]
    add(run["base_url"] + "/   " + str(pages) + (" page" if pages == 1 else " pages") + " sampled")
    add("")
    for key, label in (("access", "ACCESS     "), ("readability", "READABILITY")):
        entry = scores[key]
        add("  " + label + "   " + format(entry["score"], "g") + "/100  " + entry["letter"])
        if entry["cap_applied"]:
            add(
                "  CRITICAL      capped at "
                + format(entry["score"], "g")
                + ": "
                + entry["cap_applied"]
            )
    add("")
    add(
        "  Training posture: "
        + posture["state"]
        + " ("
        + str(posture["allowed"])
        + " of "
        + str(posture["total"])
        + " allowed)"
    )
    signals = payload.get("content_signals")
    if signals:
        add("  Content signals: " + signals["summary"])
    add("  Informational only. Blocking model training is a business decision and")
    add("  costs no points here.")
    add("")

    add(RULE)
    out += _bucket_block(payload, "citation", "CITATION CRAWLERS")
    out += _bucket_block(payload, "user_fetch", "USER FETCH CRAWLERS")
    out += _actions_block(payload)

    for category, heading in (("access", "ACCESS CHECKS"), ("readability", "READABILITY CHECKS")):
        add(RULE)
        add(heading)
        for check in (c for c in payload["checks"] if c["category"] == category):
            add(
                "  "
                + format(check["earned"], "g").rjust(6)
                + " / "
                + str(check["weight"]).ljust(3)
                + "  "
                + check["severity"].ljust(8)
                + "  "
                + check["check_id"]
            )
            add("          " + check["evidence"])
        add("")

    add(RULE)
    add("NOTES")
    add("  Sitemap: " + (payload["sitemap"]["reachable"] or "none found"))
    for page in payload["pages"]:
        add("  page " + str(page["status"]) + "  " + page["url"])
    for error in payload["errors"]:
        add("  " + error)
    add("")
    add("LIMITATIONS")
    for limitation in payload["limitations"]:
        add("  " + limitation)
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        site = build_site(args.domain, pages=args.pages)
    except SiteUnavailable as exc:
        print("geo-check: " + exc.domain + ": " + exc.reason, file=sys.stderr)
        print(ABORT_NOTE.get(status_in(exc.reason), GENERIC_ABORT_NOTE), file=sys.stderr)
        return EXIT_ABORTED

    results = run_all(site)
    access = score_category(results, Category.ACCESS, caps=collect_caps(site))
    # No caps on Readability. Every critical failure in the rubric is about
    # reachability, and a readable page nobody can fetch is already capped on
    # the other score.
    readability = score_category(results, Category.READABILITY)
    payload = build(site, results, access, readability)

    print(render_text(payload))

    if args.json_path:
        path = Path(args.json_path)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("\nJSON written to " + str(path))
    if args.md_path:
        path = Path(args.md_path)
        path.write_text(render_markdown(payload), encoding="utf-8")
        print("Markdown report written to " + str(path))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
