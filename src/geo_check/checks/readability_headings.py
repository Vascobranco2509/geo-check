"""Heading structure. 15 points.

Headings are the outline a retrieval system uses to decide which part of a page
answers a question. One h1 says what the page is about, and levels that descend
in order say which passage belongs to which idea. A page that jumps from h1 to
h4 reads, to a machine, as one undifferentiated block.
"""

from __future__ import annotations

from itertools import pairwise

from ..models import Category, CheckResult, Fix, PageContext, Severity, SiteContext, check_meta
from ..scoring import READABILITY_WEIGHTS


def _short(url: str, limit: int = 60) -> str:
    """Evidence lines are read in a terminal. A full news URL fills three."""
    return url if len(url) <= limit else url[: limit - 3] + "..."


CHECK_ID = "heading_structure"
DOCS = "https://developers.google.com/search/docs/fundamentals/seo-starter-guide"

# One h1 is worth more than a tidy descent, so the split is not even.
WEIGHT_SINGLE_H1 = 0.6
WEIGHT_NO_SKIPS = 0.4


def outline(page: PageContext) -> list[int]:
    """Heading levels in document order."""
    return [int(tag.name[1]) for tag in page.soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])]


def skipped_levels(levels: list[int]) -> list[tuple[int, int]]:
    """Pairs where the outline jumps down more than one level at a time."""
    return [(a, b) for a, b in pairwise(levels) if b > a + 1]


def score_page(page: PageContext) -> tuple[float, str]:
    levels = outline(page)
    h1_count = levels.count(1)
    if h1_count == 0:
        return 0.0, "no h1"

    score = WEIGHT_SINGLE_H1 if h1_count == 1 else 0.0
    notes = [] if h1_count == 1 else [str(h1_count) + " h1 elements"]

    jumps = skipped_levels(levels)
    if jumps:
        described = ", ".join("h" + str(a) + " to h" + str(b) for a, b in jumps[:3])
        notes.append("skips " + described)
    else:
        score += WEIGHT_NO_SKIPS

    return score, ", ".join(notes) if notes else "one h1, no skipped levels"


@check_meta(CHECK_ID, Category.READABILITY, READABILITY_WEIGHTS[CHECK_ID])
def heading_structure(site: SiteContext) -> CheckResult:
    pages = site.readable_pages
    if not pages:
        return CheckResult(
            check_id=CHECK_ID,
            category=Category.READABILITY,
            ratio=0.0,
            severity=Severity.WARNING,
            title="Heading structure",
            evidence="No page answered 200, so no markup could be read.",
        )

    scored = [(page, *score_page(page)) for page in pages]
    ratio = sum(score for _, score, _ in scored) / len(scored)
    faults = [(page, note) for page, score, note in scored if score < 1.0]

    fix = None
    if not faults:
        evidence = "All " + str(len(pages)) + " pages have a single h1 and no skipped levels."
        severity = Severity.OK
    else:
        listed = "; ".join(_short(page.url) + " (" + note + ")" for page, note in faults[:4])
        evidence = f"{len(faults)} of {len(pages)} pages have an outline fault: {listed}."
        severity = Severity.WARNING if ratio < 0.5 else Severity.INFO
        fix = Fix(
            summary=(
                "Give every page exactly one h1 naming what the page is about, then"
                " descend one level at a time. Making a heading look smaller is a job"
                " for CSS, not a reason to drop two levels."
            ),
            docs_url=DOCS,
        )

    return CheckResult(
        check_id=CHECK_ID,
        category=Category.READABILITY,
        ratio=ratio,
        severity=severity,
        title="Heading structure",
        evidence=evidence,
        fix=fix,
        details={
            "pages": len(pages),
            "faults": [{"url": page.url, "note": note} for page, note in faults],
        },
    )
