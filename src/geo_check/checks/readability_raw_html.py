"""Content present in raw HTML, without JavaScript. 30 points.

The heaviest check in the Readability rubric, and a heuristic. It does not
render anything. It measures how much readable text arrives in the initial HTML
response and how much of that response is script, then infers whether a crawler
that does not execute JavaScript would find anything worth quoting.

The thresholds come from measurement, not from taste. scripts/calibrate_js_threshold.py
sampled 22 live pages and wrote the numbers to data/js_calibration.csv. Two cuts
separated the sample cleanly:

  Text below 500 characters. The three known client rendered pages measured 32,
  86 and 427 characters. Nothing server rendered came in below 1463.

  Script to text ratio above 100. This caught jn.pt at 244 and dn.pt at 335,
  two news homepages that ship almost no text and load the articles
  afterwards. Every genuinely server rendered page in the sample sat below 35.

An empty mount point, a div with id root or app and nothing inside it, was
tested as a third signal and dropped. It found nothing the text rule had not
already found, and it would misfire on a server rendered page that mounts a
widget into an empty container.

The limit of all this is real and stated in the report: a page can pass here and
still hide its content behind an interaction, and a legitimately short page can
be marked down for being short.
"""

from __future__ import annotations

from ..models import Category, CheckResult, Fix, PageContext, Severity, SiteContext, check_meta
from ..scoring import READABILITY_WEIGHTS


def _short(url: str, limit: int = 60) -> str:
    """Evidence lines are read in a terminal. A full news URL fills three."""
    return url if len(url) <= limit else url[: limit - 3] + "..."


CHECK_ID = "raw_html_content"
DOCS = (
    "https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics"
)

MIN_TEXT_CHARS = 500
THIN_TEXT_CHARS = 1500
MAX_SCRIPT_TO_TEXT = 100

SCORE_EMPTY = 0.0
SCORE_SCRIPT_HEAVY = 0.25
SCORE_THIN = 0.5
SCORE_FULL = 1.0


def script_chars(page: PageContext) -> int:
    return sum(len(tag.get_text() or "") for tag in page.soup.find_all("script"))


def score_page(page: PageContext) -> tuple[float, str]:
    """A score and the reason for it, in the numbers the reason rests on."""
    text = len(page.text)
    scripts = script_chars(page)
    ratio = scripts / text if text else float("inf")

    if text < MIN_TEXT_CHARS:
        return SCORE_EMPTY, f"{text} characters of text in the raw HTML, effectively empty"
    if ratio > MAX_SCRIPT_TO_TEXT:
        return (
            SCORE_SCRIPT_HEAVY,
            f"{text} characters of text against {scripts} of script, a ratio of {ratio:.0f} to 1",
        )
    if text < THIN_TEXT_CHARS:
        return SCORE_THIN, f"only {text} characters of text in the raw HTML"
    return SCORE_FULL, f"{text} characters of text in the raw HTML"


@check_meta(CHECK_ID, Category.READABILITY, READABILITY_WEIGHTS[CHECK_ID])
def raw_html_content(site: SiteContext) -> CheckResult:
    pages = site.readable_pages
    if not pages:
        return CheckResult(
            check_id=CHECK_ID,
            category=Category.READABILITY,
            ratio=0.0,
            severity=Severity.WARNING,
            title="Content in raw HTML",
            evidence="No page answered 200, so nothing could be measured.",
        )

    scored = [(page, *score_page(page)) for page in pages]
    ratio = sum(score for _, score, _ in scored) / len(scored)
    weak = [(page, note) for page, score, note in scored if score < SCORE_FULL]

    fix = None
    if not weak:
        evidence = (
            "All "
            + str(len(pages))
            + " sampled pages carry their content in the initial HTML response."
        )
        severity = Severity.OK
    else:
        listed = "; ".join(_short(page.url) + " (" + note + ")" for page, note in weak[:4])
        evidence = (
            str(len(weak))
            + " of "
            + str(len(pages))
            + " sampled pages arrive without much readable content: "
            + listed
            + ". This is a heuristic based on text volume and script weight, not"
            " real rendering."
        )
        severity = Severity.CRITICAL if ratio < 0.34 else Severity.WARNING
        fix = Fix(
            summary=(
                "Serve the main content in the first HTML response, through server"
                " side rendering, static generation or prerendering for crawlers."
                " Most AI crawlers do not run JavaScript, so whatever the browser"
                " assembles afterwards is invisible to them."
            ),
            docs_url=DOCS,
        )

    return CheckResult(
        check_id=CHECK_ID,
        category=Category.READABILITY,
        ratio=ratio,
        severity=severity,
        title="Content in raw HTML",
        evidence=evidence,
        fix=fix,
        details={
            "pages": len(pages),
            "heuristic": True,
            "thresholds": {
                "min_text_chars": MIN_TEXT_CHARS,
                "thin_text_chars": THIN_TEXT_CHARS,
                "max_script_to_text": MAX_SCRIPT_TO_TEXT,
            },
            "weak": [{"url": page.url, "note": note} for page, note in weak],
        },
    )
