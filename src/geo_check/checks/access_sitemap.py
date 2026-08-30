"""Sitemap declared and reachable. 10 points.

Declared and broken is a different problem from never declared, and gets a
different fix, so the two are reported apart.
"""

from __future__ import annotations

from ..models import Category, CheckResult, Fix, Severity, SiteContext, check_meta
from ..scoring import ACCESS_WEIGHTS

CHECK_ID = "sitemap_available"
DOCS = "https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap"


@check_meta(CHECK_ID, Category.ACCESS, ACCESS_WEIGHTS[CHECK_ID])
def sitemap_available(site: SiteContext) -> CheckResult:
    declared = site.sitemap_declared_url
    found = site.sitemap_url

    if found and declared:
        return CheckResult(
            check_id=CHECK_ID,
            category=Category.ACCESS,
            ratio=1.0,
            severity=Severity.OK,
            title="Sitemap available",
            evidence=f"robots.txt declares {declared} and it answers with a sitemap.",
            details={"declared": declared, "reachable": found},
        )

    if found:
        return CheckResult(
            check_id=CHECK_ID,
            category=Category.ACCESS,
            ratio=1.0,
            severity=Severity.INFO,
            title="Sitemap available",
            evidence=(
                f"A sitemap answers at {found}, but robots.txt does not declare it."
                " Crawlers that do not guess the conventional path will miss it."
            ),
            fix=Fix(
                summary="Declare the sitemap in robots.txt so no crawler has to guess.",
                snippet=f"Sitemap: {found}",
                docs_url=DOCS,
            ),
            details={"declared": None, "reachable": found},
        )

    if declared:
        return CheckResult(
            check_id=CHECK_ID,
            category=Category.ACCESS,
            ratio=0.0,
            severity=Severity.WARNING,
            title="Sitemap available",
            evidence=(
                f"robots.txt declares {declared} but that URL did not answer with a"
                " sitemap. A declared sitemap that does not load is worse than none,"
                " because crawlers stop looking."
            ),
            fix=Fix(
                summary=(
                    "Fix or remove the declared sitemap URL. Check that it returns 200"
                    " with XML and not an HTML error page."
                ),
                docs_url=DOCS,
            ),
            details={"declared": declared, "reachable": None},
        )

    return CheckResult(
        check_id=CHECK_ID,
        category=Category.ACCESS,
        ratio=0.0,
        severity=Severity.WARNING,
        title="Sitemap available",
        evidence=(f"No sitemap declared in robots.txt and nothing at {site.base_url}/sitemap.xml."),
        fix=Fix(
            summary=(
                "Publish a sitemap and declare it in robots.txt. Without one, a crawler"
                " only finds pages it can reach by following links."
            ),
            snippet=f"Sitemap: {site.base_url}/sitemap.xml",
            docs_url=DOCS,
        ),
        details={"declared": None, "reachable": None},
    )
