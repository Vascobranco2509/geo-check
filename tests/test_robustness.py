"""The 500 site robustness run, replayed offline.

CLAUDE.md asks for above 95 percent completing, with the rest failing for a
logged reason. Failing with a reason counts as the tool working: a site behind a
bot manager cannot be audited by anyone, and saying so is the honest result.

These fixtures are not in the repository. 500 sites of real HTML is 208 MB, and
truncating the pages was measured and rejected, because at a 300 KB cap 6 of 12
domains changed their Readability score. So the corpus fixtures are recorded
locally and this file skips when they are absent. The golden set, which is
committed, is what a fresh clone runs.

Record them with:

    python scripts/refresh_fixtures.py --out tests/fixtures/corpus \
        --report data/robustness_report.json
"""

from functools import cache
from pathlib import Path

import pytest

from geo_check.checks import run_all
from geo_check.cli import collect_caps
from geo_check.fixtures import Replayer, available, load
from geo_check.models import Category
from geo_check.report.json_out import build
from geo_check.report.markdown import render
from geo_check.scoring import score_category
from geo_check.site import SiteUnavailable, build_site

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "corpus"
CORPUS = ROOT / "data" / "corpus_500.txt"
MINIMUM_COMPLETION = 95.0

RECORDED = available(FIXTURES)
# Replaying 500 sites takes minutes, so it is opt in even when the
# fixtures are on disk. CLAUDE.md asks for a suite that runs in seconds, and a
# slow default is a suite people stop running.
needs_fixtures = pytest.mark.skipif(
    len(RECORDED) < 50,
    reason="corpus fixtures not recorded, run scripts/refresh_fixtures.py",
)
slow = pytest.mark.slow


def read_corpus() -> list[str]:
    lines = (
        line.split("#", 1)[0].strip() for line in CORPUS.read_text(encoding="utf-8").splitlines()
    )
    return [line for line in lines if line]


@cache
def audit(domain: str) -> tuple[str, str]:
    """Returns (outcome, detail). Never raises, which is the whole point.

    Cached because three tests walk the same 500 sites, and replaying a site
    means parsing five real pages.
    """
    try:
        site = build_site(domain, pages=5, fetcher=Replayer(load(FIXTURES, domain)["responses"]))
    except SiteUnavailable as exc:
        return "aborted", exc.reason
    results = run_all(site)
    access = score_category(results, Category.ACCESS, caps=collect_caps(site))
    readability = score_category(results, Category.READABILITY)
    payload = build(site, results, access, readability)
    render(payload)
    return "scored", str(payload["scores"]["access"]["score"])


def test_the_corpus_is_five_hundred_unique_domains():
    """The corpus is the input the robustness claim rests on, so it is asserted."""
    domains = read_corpus()
    assert len(domains) == 500
    assert len(set(domains)) == 500


@slow
@needs_fixtures
def test_the_whole_corpus_completes_or_says_why():
    """Completing means the tool handled the site, not that the site answered.

    CLAUDE.md is explicit that failing with a logged reason counts as working.
    Roughly a fifth of the corpus sits behind a bot manager that refuses a
    browser as readily as it refuses this tool, and no auditor can score those.
    What must never happen is a traceback, or an abort with no reason attached.
    """
    scored, aborted, crashed = [], [], []
    for domain in RECORDED:
        try:
            outcome, detail = audit(domain)
        except Exception as exc:  # noqa: BLE001 - a crash here is the finding
            crashed.append((domain, type(exc).__name__ + ": " + str(exc)))
            continue
        (scored if outcome == "scored" else aborted).append((domain, detail))

    assert not crashed, crashed[:5]
    assert all(detail for _, detail in aborted), "an abort with no reason is a crash in disguise"

    handled = 100 * (len(scored) + len(aborted)) / len(RECORDED)
    assert handled >= MINIMUM_COMPLETION, f"{handled:.1f} percent handled"


@slow
@needs_fixtures
def test_enough_of_the_corpus_actually_scores_to_support_a_study():
    """Not a claim about the tool. A floor under the sample the study rests on.

    Measured at 81 percent over a 42 domain spread. The floor is set well below
    that so a bad week on the open web does not turn into a red test, but low
    enough that a real collapse in coverage is noticed.
    """
    scored = sum(1 for domain in RECORDED if audit(domain)[0] == "scored")
    share = 100 * scored / len(RECORDED)
    assert share >= 60, f"only {share:.1f} percent scored, the corpus no longer supports a study"


@slow
@needs_fixtures
def test_no_site_produces_a_score_outside_zero_to_one_hundred():
    for domain in RECORDED:
        outcome, detail = audit(domain)
        if outcome == "scored":
            assert 0 <= float(detail) <= 100, (domain, detail)
