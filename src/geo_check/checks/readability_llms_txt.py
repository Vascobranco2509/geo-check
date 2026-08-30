"""llms.txt present with real content. 5 points.

llms.txt is a proposed convention, not a standard anyone is obliged to follow,
and no major vendor has committed to reading it. It is worth 5 points and not
more for exactly that reason. What it does buy is a curated map of the site
written for a machine, which costs an afternoon.

An empty file, or a placeholder, scores nothing. So does a 404 handler that
answers 200 with a page, which is why the body is inspected rather than trusted.
"""

from __future__ import annotations

from ..models import Category, CheckResult, Fix, Severity, SiteContext, check_meta
from ..scoring import READABILITY_WEIGHTS

CHECK_ID = "llms_txt"
DOCS = "https://llmstxt.org/"

# Short enough to be generous, long enough to reject a placeholder.
MIN_CONTENT_CHARS = 100

TEMPLATE = """# Site name

> One paragraph saying what this site is and who it is for.

## Core pages

- [What we do](https://example.pt/servicos): one line on what is there
- [Pricing](https://example.pt/precos): one line on what is there

## Documentation

- [Getting started](https://example.pt/docs/inicio): one line on what is there"""


@check_meta(CHECK_ID, Category.READABILITY, READABILITY_WEIGHTS[CHECK_ID])
def llms_txt(site: SiteContext) -> CheckResult:
    body = (site.llms_txt or "").strip()
    url = site.base_url + "/llms.txt"

    if not body:
        return CheckResult(
            check_id=CHECK_ID,
            category=Category.READABILITY,
            ratio=0.0,
            severity=Severity.INFO,
            title="llms.txt",
            evidence="No llms.txt at " + url + ".",
            fix=Fix(
                summary=(
                    "Publish an llms.txt listing the pages worth reading, one line"
                    " each. It is a proposal rather than a standard, so treat it as"
                    " cheap insurance and not as a priority."
                ),
                snippet=TEMPLATE,
                docs_url=DOCS,
            ),
            details={"present": False, "length": 0},
        )

    if len(body) < MIN_CONTENT_CHARS:
        return CheckResult(
            check_id=CHECK_ID,
            category=Category.READABILITY,
            ratio=0.0,
            severity=Severity.INFO,
            title="llms.txt",
            evidence=(
                "llms.txt exists at "
                + url
                + " but holds only "
                + str(len(body))
                + " characters, which reads as a placeholder rather than a map."
            ),
            fix=Fix(
                summary="Fill in llms.txt with the pages that actually matter.",
                snippet=TEMPLATE,
                docs_url=DOCS,
            ),
            details={"present": True, "length": len(body)},
        )

    return CheckResult(
        check_id=CHECK_ID,
        category=Category.READABILITY,
        ratio=1.0,
        severity=Severity.OK,
        title="llms.txt",
        evidence="llms.txt present at " + url + ", " + str(len(body)) + " characters.",
        details={"present": True, "length": len(body)},
    )
