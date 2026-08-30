"""Measure how often geo-check is right, not just how often it finishes.

The robustness run says the tool handles a site without falling over. It says
nothing about whether the answer is correct. This compares three independent
readings of the same robots.txt, for every agent, across the whole corpus.

  A  the tool, geo_check.robots.classify
  B  the standard library, urllib.robotparser, on the raw file
  C  a literal reader written here from the specification, sharing no code with
     either of the others

What B is worth is worth stating up front. On `User-agent: bot` the stdlib
blocks GPTBot, Googlebot and OAI-SearchBot. On `User-agent: Fetch` it blocks
Meta-ExternalFetcher. Both are wrong, both are the substring matching bug the
golden set caught in protego, and geo-check gets both right. So a disagreement
with B is expected and is evidence for the tool; a disagreement the other way is
a defect.

Three implementations agreeing proves consistency, not correctness. The number
worth publishing is the count of verdicts confirmed by hand, which this script
lists rather than computes.

    python scripts/verify_accuracy.py --out data/accuracy_report.json
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.robotparser import RobotFileParser

from geo_check.fixtures import Replayer, available, load
from geo_check.robots import classify, load_agents
from geo_check.site import SiteUnavailable, build_site

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data" / "corpus_500.txt"
FIXTURES = ROOT / "tests" / "fixtures" / "corpus"

_UA_LINE = re.compile(r"^\s*user-agent\s*:\s*(.*?)\s*$", re.IGNORECASE)
_RULE_LINE = re.compile(r"^\s*(allow|disallow)\s*:\s*(.*?)\s*$", re.IGNORECASE)


def read_corpus() -> list[str]:
    lines = (
        line.split("#", 1)[0].strip() for line in CORPUS.read_text(encoding="utf-8").splitlines()
    )
    return [line for line in lines if line]


def _matches_root(pattern: str) -> bool:
    """Does this path pattern cover the site root.

    Written from the specification rather than borrowed. A pattern matches by
    prefix, `*` stands for any run of characters, and a trailing `$` anchors the
    end. An empty pattern matches nothing, which is how `Disallow:` grants
    everything.
    """
    if not pattern:
        return False
    anchored = pattern.endswith("$")
    body = pattern[:-1] if anchored else pattern
    regex = "".join(".*" if ch == "*" else re.escape(ch) for ch in body)
    return (
        re.fullmatch(regex + "$", "/") is not None if anchored else re.match(regex, "/") is not None
    )


def literal_verdict(robots_txt: str, token: str) -> bool:
    """Oracle C. May this agent fetch the site root, read straight off the file.

    A group is a run of user-agent lines followed by a run of rule lines. A group
    applies when its value is a case-insensitive prefix of the crawler token, and
    the longest such value wins. `*` is the fallback. Inside the winning group,
    the longest matching pattern decides, and Allow beats Disallow on a tie.
    """
    groups: list[tuple[list[str], list[tuple[str, str]]]] = []
    agents: list[str] = []
    rules: list[tuple[str, str]] = []
    collecting = False
    for raw in robots_txt.splitlines():
        line = raw.split("#", 1)[0]
        ua = _UA_LINE.match(line)
        if ua:
            if not collecting:
                if agents:
                    groups.append((agents, rules))
                agents, rules = [], []
                collecting = True
            agents.append(ua.group(1))
            continue
        # Any line that is not a user-agent line closes the run of agents, even
        # one this reader does not keep. eventbrite.com puts a bare Crawl-delay
        # between two groups, and treating it as invisible merges them.
        if ":" in line:
            collecting = False
        rule = _RULE_LINE.match(line)
        if rule and agents:
            rules.append((rule.group(1).lower(), rule.group(2)))
    if agents:
        groups.append((agents, rules))

    lowered = token.lower()
    winning, best = None, -1
    for names, _ in groups:
        for name in names:
            candidate = name.lower()
            if candidate != "*" and lowered.startswith(candidate) and len(candidate) > best:
                winning, best = candidate, len(candidate)
    if winning is None:
        winning = "*"

    # Section 2.2.1: every group declaring the winning value is merged into one.
    # This harness flagged the divergence before either side implemented it, and
    # the specification settled which side was wrong. It was ours.
    applicable = [
        rule
        for names, group_rules in groups
        if any(name.lower() == winning for name in names)
        for rule in group_rules
    ]
    if not any(any(name.lower() == winning for name in names) for names, _ in groups):
        return True

    decision, length = True, -1
    for kind, pattern in applicable:
        if not _matches_root(pattern):
            continue
        size = len(pattern)
        if size > length or (size == length and kind == "allow"):
            decision, length = kind == "allow", size
    return decision


def stdlib_verdict(robots_txt: str, token: str) -> bool:
    """Oracle B. The standard library, on the raw file, warts and all."""
    parser = RobotFileParser()
    parser.parse(robots_txt.splitlines())
    return parser.can_fetch(token, "https://example.invalid/")


def compare(domain: str) -> dict | None:
    """Three readings of one site. None when the site never gave us a robots.txt."""
    try:
        site = build_site(domain, pages=1, fetcher=Replayer(load(FIXTURES, domain)["responses"]))
    except SiteUnavailable as exc:
        return {"domain": domain, "outcome": "aborted", "reason": exc.reason}
    if not site.robots_is_real or not site.robots_txt:
        return {"domain": domain, "outcome": "no robots.txt"}

    robots = site.robots_txt
    tool = {v.token: v.allowed for v in classify(robots, site.base_url)}
    rows = []
    for agent in load_agents():
        token = agent["token"]
        rows.append(
            {
                "token": token,
                "bucket": agent["bucket"],
                "tool": tool[token],
                "literal": literal_verdict(robots, token),
                "stdlib": stdlib_verdict(robots, token),
            }
        )
    return {"domain": domain, "outcome": "compared", "verdicts": rows}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare three readings of every robots.txt.")
    parser.add_argument("--out", default=str(ROOT / "data" / "accuracy_report.json"))
    args = parser.parse_args(argv)

    on_disk = set(available(FIXTURES))
    domains = [d for d in read_corpus() if d in on_disk]
    results = [compare(domain) for domain in domains]

    compared = [r for r in results if r and r["outcome"] == "compared"]
    total = agree_literal = agree_stdlib = 0
    literal_gaps: list[dict] = []
    stdlib_gaps: list[dict] = []
    for entry in compared:
        for row in entry["verdicts"]:
            total += 1
            if row["tool"] == row["literal"]:
                agree_literal += 1
            else:
                literal_gaps.append({"domain": entry["domain"], **row})
            if row["tool"] == row["stdlib"]:
                agree_stdlib += 1
            else:
                stdlib_gaps.append({"domain": entry["domain"], **row})

    blocking = sorted(
        entry["domain"]
        for entry in compared
        if any(not row["tool"] for row in entry["verdicts"] if row["bucket"] != "training")
    )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "corpus": len(domains),
        "compared": len(compared),
        "skipped": dict(
            Counter(r["outcome"] for r in results if r and r["outcome"] != "compared").most_common()
        ),
        "verdicts": total,
        "tool_vs_literal": {
            "agree": agree_literal,
            "share": round(100 * agree_literal / total, 2) if total else 0.0,
            "disagreements": literal_gaps,
        },
        "tool_vs_stdlib": {
            "agree": agree_stdlib,
            "share": round(100 * agree_stdlib / total, 2) if total else 0.0,
            "note": (
                "The standard library matches user agents by substring, so a group"
                " named bot captures GPTBot and a group named Fetch captures"
                " Meta-ExternalFetcher. Disagreements here are expected and are"
                " evidence for the tool. A disagreement the other way is a defect."
            ),
            "disagreements": stdlib_gaps,
        },
        "needs_hand_check": {
            "note": (
                "Three implementations agreeing proves consistency, not correctness."
                " These are the sites where the tool reports a block, so these are"
                " the verdicts that carry the score and have to be read by a human"
                " against the robots.txt."
            ),
            "sites_reporting_a_block": blocking,
        },
    }
    Path(args.out).write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(f"{len(domains)} domains, {len(compared)} with a real robots.txt, {total} verdicts")
    print(
        f"  tool vs literal reader   {report['tool_vs_literal']['share']:6.2f}%  "
        f"({len(literal_gaps)} disagreements)"
    )
    print(
        f"  tool vs standard library {report['tool_vs_stdlib']['share']:6.2f}%  "
        f"({len(stdlib_gaps)} disagreements, expected)"
    )
    print(f"  sites reporting a block, for hand checking: {len(blocking)}")
    print("  written to " + args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
