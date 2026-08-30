"""Canonical present and consistent. 5 points.

A canonical pointing at another host hands the citation to that host. It happens
more often than it should, usually after a staging environment ships its own
link tag to production.
"""

from __future__ import annotations

from urllib.parse import urljoin, urlsplit

from ..models import Category, CheckResult, Fix, PageContext, Severity, SiteContext, check_meta
from ..scoring import READABILITY_WEIGHTS


def _short(url: str, limit: int = 60) -> str:
    """Evidence lines are read in a terminal. A full news URL fills three."""
    return url if len(url) <= limit else url[: limit - 3] + "..."


CHECK_ID = "canonical"
DOCS = "https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls"


def canonical_of(page: PageContext) -> str:
    tag = page.soup.find(
        "link",
        attrs={
            "rel": lambda v: (
                v and "canonical" in [x.lower() for x in (v if isinstance(v, list) else [v])]
            )
        },
    )
    if tag is None:
        return ""
    href = (tag.get("href") or "").strip()
    return urljoin(page.url, href) if href else ""


def fault_on(page: PageContext) -> str | None:
    """Why this canonical is unusable, or None when it is fine."""
    href = canonical_of(page)
    if not href:
        return "no canonical"
    if urlsplit(href).netloc != urlsplit(page.url).netloc:
        return "canonical points to another host: " + href
    return None


@check_meta(CHECK_ID, Category.READABILITY, READABILITY_WEIGHTS[CHECK_ID])
def canonical(site: SiteContext) -> CheckResult:
    pages = site.readable_pages
    if not pages:
        return CheckResult(
            check_id=CHECK_ID,
            category=Category.READABILITY,
            ratio=0.0,
            severity=Severity.WARNING,
            title="Canonical",
            evidence="No page answered 200, so no markup could be read.",
        )

    faults = [(page, fault) for page in pages if (fault := fault_on(page))]
    ratio = (len(pages) - len(faults)) / len(pages)

    fix = None
    if not faults:
        evidence = "All " + str(len(pages)) + " pages declare a canonical on their own host."
        severity = Severity.OK
    else:
        listed = "; ".join(_short(page.url) + " (" + fault + ")" for page, fault in faults[:4])
        evidence = f"{len(faults)} of {len(pages)} pages have a canonical fault: {listed}."
        severity = Severity.WARNING
        fix = Fix(
            summary=(
                "Add a self referencing canonical to every page, with an absolute URL"
                " on the site's own host. Check that the deployed value is not still"
                " pointing at a staging domain."
            ),
            snippet='<link rel="canonical" href="https://example.pt/this-exact-page">',
            docs_url=DOCS,
        )

    return CheckResult(
        check_id=CHECK_ID,
        category=Category.READABILITY,
        ratio=ratio,
        severity=severity,
        title="Canonical",
        evidence=evidence,
        fix=fix,
        details={
            "pages": len(pages),
            "faults": [{"url": page.url, "fault": fault} for page, fault in faults],
        },
    )
