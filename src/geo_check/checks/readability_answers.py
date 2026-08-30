"""Answer shaped content. 5 points.

Answer engines lift self contained chunks: a numbered procedure, a comparison
table, a question with its answer next to it. Prose that only makes sense in
sequence has nothing to lift.

This check reads structure, not quality. It can see that a page has an ordered
list of five steps; it cannot see whether the steps are any good. That is the
honest limit of reading markup, and the report says so. Finding three of the
six shapes anywhere in the sample earns the full five points, because this is a
light signal and was never meant to carry more.

The shapes come from the extractable content patterns in the aeo skill.
"""

from __future__ import annotations

import re

from ..models import Category, CheckResult, Fix, PageContext, Severity, SiteContext, check_meta
from ..scoring import READABILITY_WEIGHTS

CHECK_ID = "answer_shaped_content"
DOCS = "https://llmstxt.org/"

PATTERNS_FOR_FULL_MARKS = 3

# The five points split between two questions. Are there extractable shapes at
# all, and is the prose broken into pieces small enough to be lifted whole.
WEIGHT_SHAPES = 0.6
WEIGHT_BLOCKS = 0.4

# Block sizing, measured rather than borrowed. The idea comes from
# zubair-trabzada/geo-seo-claude (MIT), which scores blocks against an optimal
# band of 134 to 167 words. Measuring 12301 blocks across 868 pages of the
# corpus showed why that band cannot be used here: the median real block is 20
# words and their optimal range covers 2.6 percent of what exists. Scoring
# against it would fail almost every site without telling anyone apart.
#
# What does separate is how much of a page sits in its single largest block.
# Across the 776 pages with real prose the median is 0.40, a quarter are at or
# below 0.24, and 7 percent are effectively one undivided wall. wells.pt has a
# page of 18084 words whose largest block holds 17412 of them. The numbers are
# in data/block_calibration.csv.
MIN_WORDS_TO_JUDGE = 200
WELL_SECTIONED_SHARE = 0.35
ONE_BLOCK_SHARE = 0.80

BLOCK_TAGS = ["h1", "h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "table", "blockquote", "dl"]
MIN_STEPS = 3
MIN_TABLE_ROWS = 3
MIN_QUESTION_HEADINGS = 2

SUMMARY_MARKERS = (
    "key takeaways",
    "quick summary",
    "in short",
    "tl;dr",
    "em resumo",
    "resumo",
    "principais conclusoes",
    "principais conclusões",
    "o essencial",
)
FAQ_TYPES = {"faqpage", "qapage"}
_WHITESPACE = re.compile(r"\s+")


def _headings(page: PageContext) -> list[str]:
    tags = page.soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
    return [_WHITESPACE.sub(" ", tag.get_text(" ", strip=True)).strip() for tag in tags]


def has_steps(page: PageContext) -> bool:
    return any(
        len(ol.find_all("li", recursive=False)) >= MIN_STEPS for ol in page.soup.find_all("ol")
    )


def has_comparison_table(page: PageContext) -> bool:
    for table in page.soup.find_all("table"):
        if table.find("th") and len(table.find_all("tr")) >= MIN_TABLE_ROWS:
            return True
    return False


def has_faq(page: PageContext) -> bool:
    for block in page.jsonld:
        declared = block.get("@type")
        values = declared if isinstance(declared, list) else [declared]
        if any(isinstance(v, str) and v.strip().lower() in FAQ_TYPES for v in values):
            return True
    if page.soup.find("details") and page.soup.find("summary"):
        return True
    questions = [text for text in _headings(page) if text.endswith("?")]
    return len(questions) >= MIN_QUESTION_HEADINGS


def has_definition_list(page: PageContext) -> bool:
    return any(dl.find("dt") and dl.find("dd") for dl in page.soup.find_all("dl"))


def has_attributed_quote(page: PageContext) -> bool:
    for quote in page.soup.find_all("blockquote"):
        if quote.find("cite") or quote.get("cite"):
            return True
    return False


def block_sizes(page: PageContext) -> list[int]:
    """Words between one heading and the next, in document order."""
    sizes: list[int] = []
    running = 0
    for element in page.soup.find_all(BLOCK_TAGS):
        name = element.name
        if len(name) == 2 and name[0] == "h" and name[1].isdigit():
            if running:
                sizes.append(running)
            running = 0
        else:
            running += len(element.get_text(" ", strip=True).split())
    if running:
        sizes.append(running)
    return sizes


def citable_score(page: PageContext) -> float:
    """How liftable this page is, from 0 for one wall of text to 1 for sections.

    A page too short to have sections is not penalised. Shortness is not the
    fault being measured here, and raw_html_content already covers emptiness.
    """
    sizes = block_sizes(page)
    total = sum(sizes)
    if total < MIN_WORDS_TO_JUDGE:
        return 1.0
    share = max(sizes) / total
    if share <= WELL_SECTIONED_SHARE:
        return 1.0
    if share >= ONE_BLOCK_SHARE:
        return 0.0
    return (ONE_BLOCK_SHARE - share) / (ONE_BLOCK_SHARE - WELL_SECTIONED_SHARE)


def has_summary_box(page: PageContext) -> bool:
    return any(
        marker in heading.lower() for heading in _headings(page) for marker in SUMMARY_MARKERS
    )


DETECTORS = {
    "numbered steps": has_steps,
    "comparison table": has_comparison_table,
    "question and answer block": has_faq,
    "definition list": has_definition_list,
    "attributed quote": has_attributed_quote,
    "summary box": has_summary_box,
}


@check_meta(CHECK_ID, Category.READABILITY, READABILITY_WEIGHTS[CHECK_ID])
def answer_shaped_content(site: SiteContext) -> CheckResult:
    pages = site.readable_pages
    if not pages:
        return CheckResult(
            check_id=CHECK_ID,
            category=Category.READABILITY,
            ratio=0.0,
            severity=Severity.WARNING,
            title="Answer shaped content",
            evidence="No page answered 200, so no markup could be read.",
        )

    found = sorted(name for name, detect in DETECTORS.items() if any(detect(p) for p in pages))
    missing = sorted(name for name in DETECTORS if name not in found)
    shape_share = min(len(found), PATTERNS_FOR_FULL_MARKS) / PATTERNS_FOR_FULL_MARKS
    block_share = sum(citable_score(page) for page in pages) / len(pages)
    walls = [page for page in pages if citable_score(page) == 0.0]
    ratio = WEIGHT_SHAPES * shape_share + WEIGHT_BLOCKS * block_share

    if found:
        evidence = (
            "Found "
            + str(len(found))
            + " of "
            + str(len(DETECTORS))
            + " extractable shapes across the sample: "
            + ", ".join(found)
            + "."
        )
    else:
        evidence = (
            "None of the "
            + str(len(DETECTORS))
            + " extractable shapes appear anywhere in the sample."
        )
    evidence += (
        " Sectioning: "
        + str(round(100 * block_share))
        + " percent, measured as how much of each page escapes its single"
        " largest block."
    )
    if walls:
        evidence += (
            " "
            + str(len(walls))
            + " of "
            + str(len(pages))
            + " sampled pages are effectively one undivided block, which an"
            " answer engine cannot lift a passage out of."
        )

    fix = None
    if ratio < 1.0:
        fix = Fix(
            summary=(
                (
                    "Break the prose into sections with headings, so a passage can be"
                    " lifted without the rest of the page. "
                    if block_share < 1.0
                    else ""
                )
                + "Add at least "
                + str(PATTERNS_FOR_FULL_MARKS)
                + " of these shapes to the pages meant to be cited. Still missing: "
                + ", ".join(missing)
                + ". A numbered procedure and a question with its answer beneath it"
                " are the two cheapest to retrofit."
            ),
            docs_url=DOCS,
        )

    return CheckResult(
        check_id=CHECK_ID,
        category=Category.READABILITY,
        ratio=ratio,
        severity=Severity.OK if ratio == 1.0 else Severity.INFO,
        title="Answer shaped content",
        evidence=evidence,
        fix=fix,
        details={
            "found": found,
            "missing": missing,
            "shape_share": round(shape_share, 3),
            "block_share": round(block_share, 3),
            "pages_that_are_one_block": [page.url for page in walls],
            "structural_only": True,
        },
    )
