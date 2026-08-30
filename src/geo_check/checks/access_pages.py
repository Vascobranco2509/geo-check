"""Sample pages return 200 without a login wall. 15 points.

Phase 1 samples one page, the homepage. Phase 2 widens the sample and this
check does not change, it just receives more pages.

The login wall test is a heuristic and the report says so. It looks for a
password field on a page with very little text, an authentication path in the
final URL after redirects, or a 401 or 403. A paywall that serves the full
article to the crawler and hides it behind CSS will pass here, correctly, since
the crawler does get the text.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from ..models import Category, CheckResult, Fix, PageContext, Severity, SiteContext, check_meta
from ..scoring import ACCESS_WEIGHTS

CHECK_ID = "pages_reachable"

LOGIN_PATH_MARKERS = (
    "/login",
    "/signin",
    "/sign-in",
    "/entrar",
    "/wp-login",
    "/auth/",
    "/conta/entrar",
    "/iniciar-sessao",
)
# A page carrying a password field and almost no prose is a gate. A page with a
# password field in the header and a full article behind it is not.
MIN_TEXT_BEHIND_A_GATE = 1500


def wall_reason(page: PageContext) -> str | None:
    """Why this page looks gated, or None when it looks readable."""
    if page.status in (401, 403):
        return f"HTTP {page.status}"
    if page.status != 200:
        return f"HTTP {page.status}"

    path = urlsplit(page.url).path.lower()
    for marker in LOGIN_PATH_MARKERS:
        if marker in path:
            return f"final URL is an authentication path: {path}"

    if page.soup.find("input", attrs={"type": "password"}) is not None:
        length = len(page.text)
        if length < MIN_TEXT_BEHIND_A_GATE:
            return f"password field with only {length} characters of visible text"
    return None


@check_meta(CHECK_ID, Category.ACCESS, ACCESS_WEIGHTS[CHECK_ID])
def pages_reachable(site: SiteContext) -> CheckResult:
    if not site.pages:
        return CheckResult(
            check_id=CHECK_ID,
            category=Category.ACCESS,
            ratio=0.0,
            severity=Severity.WARNING,
            title="Pages reachable",
            evidence="No pages were sampled, so nothing could be checked.",
        )

    gated = [(page, reason) for page in site.pages if (reason := wall_reason(page))]
    total = len(site.pages)
    reachable = total - len(gated)
    ratio = reachable / total

    if not gated:
        evidence = (
            f"{total} of {total} sampled pages returned 200 with readable content"
            " and no sign of a login wall."
        )
        severity = Severity.OK
    else:
        details = "; ".join(f"{page.url} ({reason})" for page, reason in gated)
        evidence = f"{reachable} of {total} sampled pages are readable. Gated: {details}."
        severity = Severity.WARNING if reachable else Severity.CRITICAL

    fix = None
    if gated:
        fix = Fix(
            summary=(
                "Serve the article text in the initial HTML response, even when a"
                " prompt to register sits on top of it. A crawler that receives only"
                " a login form has nothing to quote, so the page cannot be cited."
            ),
            docs_url="https://developers.google.com/search/docs/appearance/structured-data/paywalled-content",
        )

    return CheckResult(
        check_id=CHECK_ID,
        category=Category.ACCESS,
        ratio=ratio,
        severity=severity,
        title="Pages reachable",
        evidence=evidence,
        fix=fix,
        details={
            "sampled": total,
            "reachable": reachable,
            "gated": [{"url": page.url, "reason": reason} for page, reason in gated],
            "heuristic": True,
        },
    )
