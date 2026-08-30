"""Author and publication or modification dates identifiable. 10 points.

Answer engines weight attribution heavily, because a claim they cannot trace to
a person and a date is a claim they cannot defend. Most content management
systems already hold both fields and simply never put them in the markup.
"""

from __future__ import annotations

from ..models import Category, CheckResult, Fix, PageContext, Severity, SiteContext, check_meta
from ..scoring import READABILITY_WEIGHTS

CHECK_ID = "author_and_dates"
DOCS = "https://developers.google.com/search/docs/appearance/structured-data/article"

AUTHOR_META = {"author", "article:author", "twitter:creator", "dc.creator", "citation_author"}
DATE_META = {
    "article:published_time",
    "article:modified_time",
    "datepublished",
    "datemodified",
    "dc.date",
    "dc.date.issued",
    "citation_publication_date",
    "og:updated_time",
}
WEIGHT_AUTHOR = 0.5
WEIGHT_DATE = 0.5

TEMPLATE = """<meta name="author" content="Author name">
<meta property="article:published_time" content="2026-08-30T09:00:00+01:00">
<meta property="article:modified_time" content="2026-08-30T09:00:00+01:00">"""


def _meta_names(page: PageContext) -> set[str]:
    names = set()
    for meta in page.soup.find_all("meta"):
        for attribute in ("name", "property", "itemprop"):
            value = (meta.get(attribute) or "").strip().lower()
            if value and (meta.get("content") or "").strip():
                names.add(value)
    return names


def has_author(page: PageContext) -> bool:
    if _meta_names(page) & AUTHOR_META:
        return True
    for block in page.jsonld:
        author = block.get("author") or block.get("creator")
        if author:
            return True
    return bool(page.soup.select_one('[rel="author"], [itemprop="author"], .author, .byline'))


def has_date(page: PageContext) -> bool:
    if _meta_names(page) & DATE_META:
        return True
    for block in page.jsonld:
        if block.get("datePublished") or block.get("dateModified") or block.get("dateCreated"):
            return True
    return page.soup.find("time", attrs={"datetime": True}) is not None


@check_meta(CHECK_ID, Category.READABILITY, READABILITY_WEIGHTS[CHECK_ID])
def author_and_dates(site: SiteContext) -> CheckResult:
    pages = site.readable_pages
    if not pages:
        return CheckResult(
            check_id=CHECK_ID,
            category=Category.READABILITY,
            ratio=0.0,
            severity=Severity.WARNING,
            title="Author and dates",
            evidence="No page answered 200, so no markup could be read.",
        )

    with_author = [page for page in pages if has_author(page)]
    with_date = [page for page in pages if has_date(page)]
    ratio = WEIGHT_AUTHOR * (len(with_author) / len(pages)) + WEIGHT_DATE * (
        len(with_date) / len(pages)
    )

    evidence = (
        str(len(with_author))
        + " of "
        + str(len(pages))
        + " pages identify an author, and "
        + str(len(with_date))
        + " identify a publication or modification date."
    )

    fix = None
    if ratio < 1.0:
        fix = Fix(
            summary=(
                "Publish the author and the dates in the markup, not only in the"
                " rendered page. The JSON-LD Article block is the strongest place"
                " for it, and these meta tags are the cheapest."
            ),
            snippet=TEMPLATE,
            docs_url=DOCS,
        )

    return CheckResult(
        check_id=CHECK_ID,
        category=Category.READABILITY,
        ratio=ratio,
        severity=Severity.OK if ratio == 1.0 else Severity.WARNING,
        title="Author and dates",
        evidence=evidence,
        fix=fix,
        details={
            "pages": len(pages),
            "with_author": len(with_author),
            "with_date": len(with_date),
        },
    )
