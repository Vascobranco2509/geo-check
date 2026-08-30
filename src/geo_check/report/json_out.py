"""JSON output.

This is the real result of a run. The markdown report and the text printed in
the terminal are both rendered from this dictionary, so the three can never
disagree about the same run.

schema_version is here from day one. Comparing runs over time is out of scope
for v1, but a JSON file without a version is a file nobody can safely parse
later.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .. import __version__
from ..models import Bucket, Category, CheckResult, SiteContext
from ..robots import allow_snippet, bucket_counts, is_blanket_disallow
from ..scoring import ACCESS_WEIGHTS, READABILITY_WEIGHTS, ScoreBreakdown, training_posture

SCHEMA_VERSION = 1

LIMITATIONS = [
    (
        "Blocking at the CDN or WAF level is not detected. A site can pass every"
        " check here and still return 403 to AI crawlers in practice."
    ),
    (
        "The JavaScript check does not render anything. It infers from text volume"
        " and script weight, with thresholds measured across 22 live pages and"
        " recorded in data/js_calibration.csv."
    ),
    (
        "The login wall test is a heuristic based on page structure and text"
        " volume, not a real session."
    ),
    (
        "Answer shaped content is detected structurally. The check can see that a"
        " page has an ordered list of five steps, not whether the steps are useful."
    ),
    (
        "Whether AI assistants actually cite the site is not measured. That is a"
        " different and much larger problem."
    ),
]

# The checks whose fixes are robots.txt directives, so they can be merged into
# one block the site owner pastes once.
ROBOTS_FIX_CHECKS = ("citation_crawlers_allowed", "user_fetch_crawlers_allowed")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _fix(result: CheckResult) -> dict | None:
    if result.fix is None:
        return None
    return {
        "summary": result.fix.summary,
        "snippet": result.fix.snippet,
        "docs_url": result.fix.docs_url,
    }


def _checks(results: list[CheckResult]) -> list[dict]:
    """One entry per rubric criterion, in rubric order.

    Built from the weights rather than from the results, so a check that failed
    to run appears as a zero with a reason instead of vanishing.
    """
    by_id = {result.check_id: result for result in results}
    entries: list[dict] = []
    for category, weights in (
        (Category.ACCESS, ACCESS_WEIGHTS),
        (Category.READABILITY, READABILITY_WEIGHTS),
    ):
        for check_id, weight in weights.items():
            result = by_id.get(check_id)
            if result is None:
                entries.append(
                    {
                        "check_id": check_id,
                        "category": category.value,
                        "title": check_id,
                        "weight": weight,
                        "ratio": 0.0,
                        "earned": 0.0,
                        "severity": "warning",
                        "evidence": "check did not run",
                        "fix": None,
                        "details": {},
                    }
                )
                continue
            entries.append(
                {
                    "check_id": check_id,
                    "category": category.value,
                    "title": result.title,
                    "weight": weight,
                    "ratio": round(result.ratio, 4),
                    "earned": round(weight * result.ratio, 2),
                    "severity": result.severity.value,
                    "evidence": result.evidence,
                    "fix": _fix(result),
                    "details": result.details,
                }
            )
    return entries


def _crawlers(site: SiteContext) -> dict:
    buckets: dict[str, dict] = {}
    for bucket in Bucket:
        verdicts = [v for v in site.agent_verdicts if v.bucket is bucket]
        allowed, total = bucket_counts(site.agent_verdicts, bucket)
        buckets[bucket.value] = {
            "allowed": allowed,
            "total": total,
            "agents": [
                {
                    "token": v.token,
                    "vendor": v.vendor,
                    "allowed": v.allowed,
                    "matched_rule": v.matched_rule,
                    "obeys_robots": v.obeys_robots,
                    "ai_only": v.ai_only,
                }
                for v in verdicts
            ],
        }
    return buckets


def robots_additions(results: list[CheckResult]) -> str:
    """Every robots.txt line the fixes call for, merged into one block.

    A site that blocks both citation and user fetch crawlers otherwise receives
    two separate snippets, and pasting two overlapping blocks into robots.txt is
    how people end up with contradictory groups. Agents documented as ignoring
    robots.txt are left out, because a rule aimed at them would be theatre.
    """
    by_id = {result.check_id: result for result in results}
    tokens: list[str] = []
    for check_id in ROBOTS_FIX_CHECKS:
        result = by_id.get(check_id)
        if result is None or result.fix is None:
            continue
        ineffective = set(result.details.get("blocked_but_ignore_robots", []))
        tokens.extend(t for t in result.details.get("blocked", []) if t not in ineffective)

    blocks = [allow_snippet(tokens)] if tokens else []
    sitemap = by_id.get("sitemap_available")
    if sitemap is not None and sitemap.fix and sitemap.fix.snippet.startswith("Sitemap:"):
        blocks.append(sitemap.fix.snippet)
    return "\n\n".join(blocks)


def build(
    site: SiteContext,
    results: list[CheckResult],
    access: ScoreBreakdown,
    readability: ScoreBreakdown,
) -> dict:
    """The whole run, as one serialisable dictionary."""
    training_allowed, training_total = bucket_counts(site.agent_verdicts, Bucket.TRAINING)
    llms = site.llms_txt or ""

    return {
        "schema_version": SCHEMA_VERSION,
        "tool": {"name": "geo-check", "version": __version__},
        "run": {
            "domain": site.domain,
            "base_url": site.base_url,
            "generated_at": _now(),
            "pages_sampled": len(site.pages),
        },
        "scores": {
            "access": {
                "score": access.final_score,
                "raw_score": access.raw_score,
                "letter": access.letter,
                "cap_applied": access.cap_applied,
            },
            "readability": {
                "score": readability.final_score,
                "raw_score": readability.raw_score,
                "letter": readability.letter,
                "cap_applied": readability.cap_applied,
            },
        },
        "training_posture": {
            "state": training_posture(training_allowed, training_total),
            "allowed": training_allowed,
            "total": training_total,
            "note": "Informational only. Blocking model training costs no points.",
        },
        "crawlers": _crawlers(site),
        "robots": {
            "url": site.base_url + "/robots.txt",
            "status": site.robots_status,
            "is_real": site.robots_is_real,
            "blanket_disallow": bool(site.robots_txt) and is_blanket_disallow(site.robots_txt),
        },
        "sitemap": {"declared": site.sitemap_declared_url, "reachable": site.sitemap_url},
        "llms_txt": {"present": bool(llms.strip()), "length": len(llms)},
        "pages": [{"url": page.url, "status": page.status} for page in site.pages],
        "checks": _checks(results),
        "robots_txt_additions": robots_additions(results),
        "errors": list(site.errors),
        "limitations": LIMITATIONS,
    }
