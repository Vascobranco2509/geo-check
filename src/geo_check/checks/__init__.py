"""Check registry.

Adding a check is one file in this package plus one line in REGISTRY. That is
the whole extension mechanism for v1. Do not build anything more clever.
"""

from __future__ import annotations

from ..models import CheckFn, CheckResult, SiteContext
from .access_citation import citation_crawlers_allowed
from .access_noindex import no_noindex
from .access_pages import pages_reachable
from .access_sitemap import sitemap_available
from .access_user_fetch import user_fetch_crawlers_allowed
from .readability_answers import answer_shaped_content
from .readability_author_dates import author_and_dates
from .readability_canonical import canonical
from .readability_headings import heading_structure
from .readability_jsonld import jsonld_valid
from .readability_llms_txt import llms_txt
from .readability_raw_html import raw_html_content
from .readability_title import title_and_description

REGISTRY: list[CheckFn] = [
    citation_crawlers_allowed,
    user_fetch_crawlers_allowed,
    pages_reachable,
    sitemap_available,
    no_noindex,
    raw_html_content,
    jsonld_valid,
    heading_structure,
    title_and_description,
    author_and_dates,
    canonical,
    llms_txt,
    answer_shaped_content,
]


def run_all(site: SiteContext) -> list[CheckResult]:
    """Run every registered check. One failing check never aborts the run."""
    results: list[CheckResult] = []
    for check in REGISTRY:
        try:
            results.append(check(site))
        except Exception as exc:  # noqa: BLE001 - a broken check is a data point
            site.errors.append(f"{getattr(check, 'check_id', check)}: {exc}")
    return results
