"""Valid JSON-LD with a recognised type. 20 points.

Structured data is what turns a page from prose into facts an answer engine can
lift without guessing. A block that is not valid JSON is reported separately,
because it is the most common fault and it is invisible to whoever wrote it:
the page renders perfectly and the markup is simply ignored.
"""

from __future__ import annotations

from ..models import Category, CheckResult, Fix, PageContext, Severity, SiteContext, check_meta
from ..scoring import READABILITY_WEIGHTS

CHECK_ID = "jsonld_valid"
DOCS = "https://developers.google.com/search/docs/appearance/structured-data/search-gallery"

RECOGNISED_TYPES = {
    "aboutpage",
    "article",
    "blogposting",
    "book",
    "breadcrumblist",
    "collectionpage",
    "contactpage",
    "corporation",
    "course",
    "event",
    "faqpage",
    "howto",
    "itempage",
    "jobposting",
    "localbusiness",
    "medicalwebpage",
    "newsarticle",
    "offer",
    "organization",
    "person",
    "podcastepisode",
    "product",
    "qapage",
    "recipe",
    "restaurant",
    "review",
    "scholarlyarticle",
    "service",
    "softwareapplication",
    "techarticle",
    "videoobject",
    "webpage",
    "website",
}

TEMPLATE = """<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "The title of this page",
  "author": {"@type": "Person", "name": "Author name"},
  "datePublished": "2026-08-30",
  "dateModified": "2026-08-30",
  "publisher": {"@type": "Organization", "name": "Site name"}
}
</script>"""


def types_on(page: PageContext) -> set[str]:
    """Every schema type declared on the page, lowercased. @type may be a list."""
    found: set[str] = set()
    for block in page.jsonld:
        declared = block.get("@type")
        values = declared if isinstance(declared, list) else [declared]
        for value in values:
            if isinstance(value, str) and value.strip():
                found.add(value.strip().lower())
    return found


@check_meta(CHECK_ID, Category.READABILITY, READABILITY_WEIGHTS[CHECK_ID])
def jsonld_valid(site: SiteContext) -> CheckResult:
    pages = site.readable_pages
    if not pages:
        return CheckResult(
            check_id=CHECK_ID,
            category=Category.READABILITY,
            ratio=0.0,
            severity=Severity.WARNING,
            title="Valid JSON-LD",
            evidence="No page answered 200, so no markup could be read.",
        )

    recognised: list[PageContext] = []
    unrecognised: dict[str, set[str]] = {}
    broken = 0
    for page in pages:
        broken += page.broken_jsonld
        declared = types_on(page)
        if declared & RECOGNISED_TYPES:
            recognised.append(page)
        elif declared:
            unrecognised[page.url] = declared

    ratio = len(recognised) / len(pages)
    parts = [f"{len(recognised)} of {len(pages)} pages carry JSON-LD with a recognised type."]
    if unrecognised:
        listed = "; ".join(
            url + " declares " + ", ".join(sorted(types)) for url, types in unrecognised.items()
        )
        parts.append(f"Unrecognised types found: {listed}.")
    if broken:
        parts.append(
            f"{broken} JSON-LD block(s) are not valid JSON and are ignored by every consumer."
        )

    if ratio == 1.0 and not broken:
        severity = Severity.OK
    elif ratio == 0.0:
        severity = Severity.WARNING
    else:
        severity = Severity.WARNING if broken else Severity.INFO

    fix = None
    if ratio < 1.0 or broken:
        fix = Fix(
            summary=(
                "Add one JSON-LD block per page describing what the page is."
                " Validate it, because a block with a trailing comma is discarded"
                " silently and looks identical in the browser."
            ),
            snippet=TEMPLATE,
            docs_url=DOCS,
        )

    return CheckResult(
        check_id=CHECK_ID,
        category=Category.READABILITY,
        ratio=ratio,
        severity=severity,
        title="Valid JSON-LD",
        evidence=" ".join(parts),
        fix=fix,
        details={
            "pages": len(pages),
            "with_recognised_type": len(recognised),
            "broken_blocks": broken,
            "unrecognised_types": {url: sorted(t) for url, t in unrecognised.items()},
        },
    )
