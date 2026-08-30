"""Citation crawlers allowed. 50 points, the heaviest check in the project.

These are the crawlers that decide whether a site can appear in an AI answer
at all. Blocking them is almost always accidental: someone meant to opt out of
model training, pattern matched on the word AI, and took the search crawlers
down with it.
"""

from __future__ import annotations

from ..models import (
    AgentVerdict,
    Bucket,
    Category,
    CheckResult,
    Fix,
    Severity,
    SiteContext,
    check_meta,
)
from ..robots import allow_snippet
from ..scoring import ACCESS_WEIGHTS

CHECK_ID = "citation_crawlers_allowed"


def describe(verdict: AgentVerdict) -> str:
    if verdict.matched_rule:
        return f"{verdict.token} [{verdict.matched_rule}]"
    return verdict.token


@check_meta(CHECK_ID, Category.ACCESS, ACCESS_WEIGHTS[CHECK_ID])
def citation_crawlers_allowed(site: SiteContext) -> CheckResult:
    verdicts = [v for v in site.agent_verdicts if v.bucket is Bucket.CITATION]
    total = len(verdicts)
    blocked = [v for v in verdicts if not v.allowed]
    allowed_count = total - len(blocked)
    ratio = allowed_count / total if total else 0.0

    ai_only = [v for v in verdicts if v.ai_only]
    ai_only_blocked = [v for v in ai_only if not v.allowed]
    # The crawlers that only feed AI answers are all shut out while classic
    # search still gets through. The score does not change, because the rubric
    # is fixed, but this is the failure the tool exists to find and it is
    # reported at full severity.
    ai_blackout = bool(ai_only) and len(ai_only_blocked) == len(ai_only) and allowed_count > 0

    if not blocked:
        evidence = f"All {total} citation crawlers are allowed at {site.base_url}/."
        severity = Severity.OK
    else:
        names = ", ".join(describe(v) for v in blocked)
        evidence = f"{allowed_count} of {total} citation crawlers allowed. Blocked: {names}."
        if ai_blackout:
            evidence += (
                " Every crawler that exists only to feed AI answers is blocked, while"
                " classic search crawlers still get through. The site is reachable by"
                " Google and Bing and invisible to ChatGPT, Claude and Perplexity."
            )
            severity = Severity.CRITICAL
        elif allowed_count == 0:
            severity = Severity.CRITICAL
        else:
            severity = Severity.WARNING

    fix = None
    if blocked:
        fix = Fix(
            summary=(
                "Allow the citation crawlers in robots.txt. Each group sits"
                " alongside whatever Disallow rules are already there, and none of"
                " them opens the site to model training."
            ),
            snippet=allow_snippet([v.token for v in blocked]),
            docs_url="https://developers.openai.com/api/docs/bots",
        )

    return CheckResult(
        check_id=CHECK_ID,
        category=Category.ACCESS,
        ratio=ratio,
        severity=severity,
        title="Citation crawlers allowed",
        evidence=evidence,
        fix=fix,
        details={
            "allowed": [v.token for v in verdicts if v.allowed],
            "blocked": [v.token for v in blocked],
            "ai_only_blackout": ai_blackout,
        },
    )
