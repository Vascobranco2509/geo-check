"""No noindex, in the meta robots tag and in the X-Robots-Tag header. 5 points.

The header is the one people forget. A page can look perfect in the markup and
still carry `X-Robots-Tag: noindex` from a stray server rule, usually left over
from a staging environment.
"""

from __future__ import annotations

from ..models import Category, CheckResult, Fix, PageContext, Severity, SiteContext, check_meta
from ..scoring import ACCESS_WEIGHTS

CHECK_ID = "no_noindex"
BLOCKING_DIRECTIVES = {"noindex", "none"}
# Names whose robots directives apply to the crawlers this tool cares about.
META_NAMES = {"robots", "googlebot", "bingbot", "applebot"}


def blocks_indexing(value: str) -> bool:
    """True when a directive list contains noindex or none.

    X-Robots-Tag values can be prefixed with a crawler name, as in
    `googlebot: noindex, nofollow`, so both separators are split.
    """
    for part in value.replace(";", ",").split(","):
        for token in part.split(":"):
            if token.strip().lower() in BLOCKING_DIRECTIVES:
                return True
    return False


def noindex_reasons(page: PageContext) -> list[str]:
    reasons: list[str] = []
    header = page.headers.get("x-robots-tag", "")
    if header and blocks_indexing(header):
        reasons.append(f"X-Robots-Tag: {header}")
    for meta in page.soup.find_all("meta"):
        name = (meta.get("name") or "").strip().lower()
        if name not in META_NAMES:
            continue
        content = (meta.get("content") or "").strip()
        if content and blocks_indexing(content):
            reasons.append(f'<meta name="{name}" content="{content}">')
    return reasons


@check_meta(CHECK_ID, Category.ACCESS, ACCESS_WEIGHTS[CHECK_ID])
def no_noindex(site: SiteContext) -> CheckResult:
    if not site.pages:
        return CheckResult(
            check_id=CHECK_ID,
            category=Category.ACCESS,
            ratio=0.0,
            severity=Severity.WARNING,
            title="No noindex",
            evidence="No pages were sampled, so nothing could be checked.",
        )

    flagged = [(page, reasons) for page in site.pages if (reasons := noindex_reasons(page))]
    total = len(site.pages)
    clean = total - len(flagged)
    ratio = clean / total

    if not flagged:
        evidence = (
            f"No noindex directive on any of the {total} sampled pages, in markup or headers."
        )
        severity = Severity.OK
        fix = None
    else:
        listed = "; ".join(f"{page.url} ({', '.join(reasons)})" for page, reasons in flagged)
        evidence = f"{len(flagged)} of {total} sampled pages carry a noindex directive: {listed}."
        severity = Severity.CRITICAL if clean == 0 else Severity.WARNING
        fix = Fix(
            summary=(
                "Remove the noindex directive from the pages that should be findable."
                " Check the server configuration as well as the markup, because an"
                " X-Robots-Tag header overrides anything in the HTML."
            ),
            docs_url="https://developers.google.com/search/docs/crawling-indexing/block-indexing",
        )

    return CheckResult(
        check_id=CHECK_ID,
        category=Category.ACCESS,
        ratio=ratio,
        severity=severity,
        title="No noindex",
        evidence=evidence,
        fix=fix,
        details={
            "sampled": total,
            "clean": clean,
            "flagged": [{"url": page.url, "reasons": reasons} for page, reasons in flagged],
        },
    )
