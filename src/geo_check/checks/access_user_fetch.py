"""User fetch crawlers allowed. 20 points.

These retrieve a single page when someone pastes a link into an assistant or
asks about a URL. Three of the five are documented by their own vendors as
ignoring robots.txt, so a Disallow aimed at them changes nothing in practice.
The score follows the rubric and counts them all; the evidence says plainly
which blocks are real and which are decorative.
"""

from __future__ import annotations

from ..models import Bucket, Category, CheckResult, Fix, Severity, SiteContext, check_meta
from ..robots import allow_snippet
from ..scoring import ACCESS_WEIGHTS
from .access_citation import describe

CHECK_ID = "user_fetch_crawlers_allowed"


@check_meta(CHECK_ID, Category.ACCESS, ACCESS_WEIGHTS[CHECK_ID])
def user_fetch_crawlers_allowed(site: SiteContext) -> CheckResult:
    verdicts = [v for v in site.agent_verdicts if v.bucket is Bucket.USER_FETCH]
    total = len(verdicts)
    blocked = [v for v in verdicts if not v.allowed]
    allowed_count = total - len(blocked)
    ratio = allowed_count / total if total else 0.0

    ignore_robots = [v for v in blocked if not v.block_is_effective]
    effective = [v for v in blocked if v.block_is_effective]

    if not blocked:
        evidence = f"All {total} user fetch crawlers are allowed at {site.base_url}/."
        severity = Severity.OK
    else:
        evidence = (
            f"{allowed_count} of {total} user fetch crawlers allowed."
            f" Blocked: {', '.join(describe(v) for v in blocked)}."
        )
        if ignore_robots:
            names = ", ".join(v.token for v in ignore_robots)
            evidence += (
                f" {names} are documented by their vendors as ignoring robots.txt,"
                " so those blocks do not stop the fetch. Only a server or WAF rule"
                " would, and this tool does not check that."
            )
        severity = Severity.WARNING if allowed_count else Severity.CRITICAL

    fix = None
    if effective:
        fix = Fix(
            summary=(
                "Allow the assistants that honour robots.txt to fetch a page when a"
                " person asks about it. This is a single page on request, not a crawl."
            ),
            snippet=allow_snippet([v.token for v in effective]),
            docs_url="https://support.claude.com/en/articles/8896518",
        )

    return CheckResult(
        check_id=CHECK_ID,
        category=Category.ACCESS,
        ratio=ratio,
        severity=severity,
        title="User fetch crawlers allowed",
        evidence=evidence,
        fix=fix,
        details={
            "allowed": [v.token for v in verdicts if v.allowed],
            "blocked": [v.token for v in blocked],
            "blocked_but_ignore_robots": [v.token for v in ignore_robots],
        },
    )
