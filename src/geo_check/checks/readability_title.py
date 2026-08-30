"""Title and meta description, present, unique and a reasonable length. 10 points.

Duplicated titles across a site are the usual symptom of a template that never
got wired up. They cost more than they look: a retrieval system deciding which
of four pages answers a question has nothing to tell them apart.
"""

from __future__ import annotations

from ..models import Category, CheckResult, Fix, PageContext, Severity, SiteContext, check_meta
from ..scoring import READABILITY_WEIGHTS

CHECK_ID = "title_and_description"
DOCS = "https://developers.google.com/search/docs/appearance/snippet"

TITLE_RANGE = (10, 70)
DESCRIPTION_RANGE = (50, 160)

# Present matters more than perfectly sized, so a title outside the range still
# earns half. Missing earns nothing.
PARTIAL = 0.5
WEIGHT_TITLE = 0.5
WEIGHT_DESCRIPTION = 0.3
WEIGHT_UNIQUE = 0.2


def title_of(page: PageContext) -> str:
    tag = page.soup.find("title")
    return tag.get_text(strip=True) if tag else ""


def description_of(page: PageContext) -> str:
    for meta in page.soup.find_all("meta"):
        if (meta.get("name") or "").strip().lower() == "description":
            return (meta.get("content") or "").strip()
    return ""


def score_field(value: str, bounds: tuple[int, int]) -> float:
    if not value:
        return 0.0
    low, high = bounds
    return 1.0 if low <= len(value) <= high else PARTIAL


@check_meta(CHECK_ID, Category.READABILITY, READABILITY_WEIGHTS[CHECK_ID])
def title_and_description(site: SiteContext) -> CheckResult:
    pages = site.readable_pages
    if not pages:
        return CheckResult(
            check_id=CHECK_ID,
            category=Category.READABILITY,
            ratio=0.0,
            severity=Severity.WARNING,
            title="Title and meta description",
            evidence="No page answered 200, so no markup could be read.",
        )

    titles = [title_of(page) for page in pages]
    descriptions = [description_of(page) for page in pages]

    title_score = sum(score_field(t, TITLE_RANGE) for t in titles) / len(pages)
    description_score = sum(score_field(d, DESCRIPTION_RANGE) for d in descriptions) / len(pages)

    present_titles = [t for t in titles if t]
    # No titles at all is not uniqueness. Awarding that share to a site with
    # none would hand out points for the absence of the thing being measured.
    unique = bool(present_titles) and len(set(present_titles)) == len(present_titles)
    ratio = (
        WEIGHT_TITLE * title_score
        + WEIGHT_DESCRIPTION * description_score
        + WEIGHT_UNIQUE * (1.0 if unique else 0.0)
    )

    missing_titles = [p.url for p, t in zip(pages, titles, strict=True) if not t]
    missing_descriptions = [p.url for p, d in zip(pages, descriptions, strict=True) if not d]
    long_titles = [t for t in titles if t and not TITLE_RANGE[0] <= len(t) <= TITLE_RANGE[1]]
    odd_descriptions = [
        d for d in descriptions if d and not DESCRIPTION_RANGE[0] <= len(d) <= DESCRIPTION_RANGE[1]
    ]

    parts = []
    if missing_titles:
        parts.append(str(len(missing_titles)) + " pages have no title")
    if long_titles:
        parts.append(
            str(len(long_titles))
            + " titles fall outside "
            + str(TITLE_RANGE[0])
            + " to "
            + str(TITLE_RANGE[1])
            + " characters, the longest at "
            + str(max(len(t) for t in long_titles))
        )
    if missing_descriptions:
        parts.append(str(len(missing_descriptions)) + " pages have no meta description")
    if odd_descriptions:
        parts.append(
            str(len(odd_descriptions))
            + " meta descriptions fall outside "
            + str(DESCRIPTION_RANGE[0])
            + " to "
            + str(DESCRIPTION_RANGE[1])
            + " characters"
        )
    if not unique:
        repeated = sorted({t for t in present_titles if present_titles.count(t) > 1})
        parts.append("titles repeat across pages: " + "; ".join(repeated[:3]))
    if not parts:
        parts.append(
            "All "
            + str(len(pages))
            + " pages have a title and a meta description, all distinct and within a"
            " sensible length"
        )

    fix = None
    if ratio < 1.0:
        fix = Fix(
            summary=(
                "Write one title and one meta description per page, describing that"
                " page rather than the site. Roughly 10 to 70 characters for the"
                " title and 50 to 160 for the description."
            ),
            docs_url=DOCS,
        )

    return CheckResult(
        check_id=CHECK_ID,
        category=Category.READABILITY,
        ratio=ratio,
        severity=Severity.OK if ratio == 1.0 else Severity.WARNING,
        title="Title and meta description",
        evidence=". ".join(parts) + ".",
        fix=fix,
        details={
            "pages": len(pages),
            "missing_titles": missing_titles,
            "missing_descriptions": missing_descriptions,
            "titles_outside_range": len(long_titles),
            "descriptions_outside_range": len(odd_descriptions),
            "titles_unique": unique,
        },
    )
