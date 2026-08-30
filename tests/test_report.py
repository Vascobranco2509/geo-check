"""JSON payload and the two renderers. Offline.

The point of this file is that the terminal, the JSON and the markdown all come
from one payload, so a run cannot describe itself three different ways.
"""

import json

from geo_check.checks import run_all
from geo_check.cli import collect_caps, render_text
from geo_check.models import Category, CheckResult, PageContext, Severity, SiteContext
from geo_check.report.json_out import SCHEMA_VERSION, build, robots_additions
from geo_check.report.markdown import escape_cell, render
from geo_check.robots import classify
from geo_check.scoring import ACCESS_WEIGHTS, READABILITY_WEIGHTS, score_category

BASE = "https://example.pt"
BLOCKS_AI = (
    "User-agent: OAI-SearchBot\nDisallow: /\n\n"
    "User-agent: Perplexity-User\nDisallow: /\n\n"
    "User-agent: Claude-User\nDisallow: /\n"
)
PAGE = (
    "<html><head><title>Um titulo com tamanho razoavel</title></head>"
    "<body><h1>Ola</h1><p>" + ("palavra " * 400) + "</p></body></html>"
)


def make_site(robots_txt=BLOCKS_AI, sitemap=None):
    return SiteContext(
        domain="example.pt",
        base_url=BASE,
        robots_txt=robots_txt,
        robots_status=200 if robots_txt else 404,
        robots_is_real=robots_txt is not None,
        agent_verdicts=classify(robots_txt, BASE),
        sitemap_url=sitemap,
        sitemap_declared_url=sitemap,
        llms_txt=None,
        pages=[PageContext(url=BASE + "/", status=200, headers={}, html=PAGE)],
    )


def make_payload(site=None):
    site = site or make_site()
    results = run_all(site)
    access = score_category(results, Category.ACCESS, caps=collect_caps(site))
    readability = score_category(results, Category.READABILITY)
    return build(site, results, access, readability)


def test_the_payload_is_versioned_and_serialisable():
    payload = make_payload()
    assert payload["schema_version"] == SCHEMA_VERSION
    round_tripped = json.loads(json.dumps(payload, ensure_ascii=False))
    assert round_tripped["run"]["domain"] == "example.pt"


def test_the_checks_array_covers_both_rubrics_in_rubric_order():
    checks = make_payload()["checks"]
    assert [c["check_id"] for c in checks] == list(ACCESS_WEIGHTS) + list(READABILITY_WEIGHTS)
    for category, weights in (("access", ACCESS_WEIGHTS), ("readability", READABILITY_WEIGHTS)):
        earned = sum(c["weight"] for c in checks if c["category"] == category)
        assert earned == sum(weights.values()) == 100


def test_a_check_that_did_not_run_appears_as_a_zero_with_a_reason():
    """Vanishing would quietly shrink the denominator and flatter the site."""
    site = make_site()
    results = [r for r in run_all(site) if r.check_id != "canonical"]
    access = score_category(results, Category.ACCESS)
    readability = score_category(results, Category.READABILITY)
    entry = next(
        c
        for c in build(site, results, access, readability)["checks"]
        if c["check_id"] == "canonical"
    )
    assert entry["earned"] == 0.0
    assert entry["evidence"] == "check did not run"


def test_the_scores_carry_their_cap_and_letter():
    site = make_site("User-agent: *\nDisallow: /\n")
    payload = make_payload(site)
    assert payload["scores"]["access"]["score"] == 10
    assert payload["scores"]["access"]["letter"] == "F"
    assert payload["scores"]["access"]["cap_applied"] == "User-agent: * with Disallow: /"
    assert payload["robots"]["blanket_disallow"] is True


def test_the_merged_robots_block_leaves_out_agents_that_ignore_robots_txt():
    """A rule aimed at Perplexity-User is theatre, so it is not offered."""
    additions = make_payload()["robots_txt_additions"]
    assert "User-agent: OAI-SearchBot" in additions
    assert "User-agent: Claude-User" in additions
    assert "Perplexity-User" not in additions


def test_the_merged_robots_block_includes_the_sitemap_line():
    additions = make_payload()["robots_txt_additions"]
    assert additions.rstrip().endswith("Sitemap: " + BASE + "/sitemap.xml")


def test_nothing_to_merge_gives_an_empty_block():
    site = make_site(robots_txt=None, sitemap=BASE + "/sitemap.xml")
    assert robots_additions(run_all(site)) == ""


def test_the_training_posture_never_reaches_a_score():
    payload = make_payload()
    assert payload["training_posture"]["state"] in {"open", "partial", "closed", "unknown"}
    assert "costs no points" in payload["training_posture"]["note"]


def test_the_markdown_report_carries_what_a_stranger_needs():
    text = render(make_payload())
    assert text.startswith("# geo-check report: example.pt")
    assert "never averaged" in text
    assert "## What to change first" in text
    assert "User-agent: OAI-SearchBot" in text
    assert "## What this does not do" in text
    assert "CDN or WAF level" in text


def test_the_markdown_report_shows_the_cap_when_one_fired():
    text = render(make_payload(make_site("User-agent: *\nDisallow: /\n")))
    assert "**CRITICAL** Access is capped at 10" in text


def test_a_clean_site_gets_a_what_to_change_section_that_says_nothing_to_change():
    site = make_site(robots_txt=None)
    results = [
        CheckResult(
            check_id=check_id,
            category=category,
            ratio=1.0,
            severity=Severity.OK,
            title=check_id,
            evidence="fine",
        )
        for category, weights in (
            (Category.ACCESS, ACCESS_WEIGHTS),
            (Category.READABILITY, READABILITY_WEIGHTS),
        )
        for check_id in weights
    ]
    payload = build(
        site,
        results,
        score_category(results, Category.ACCESS),
        score_category(results, Category.READABILITY),
    )
    assert "Nothing. Every check passed." in render(payload)


def test_a_pipe_in_a_rule_does_not_split_the_table_column():
    assert escape_cell("User-agent: * | Disallow: /") == r"User-agent: * \| Disallow: /"
    assert r"\|" in render(make_payload())


def test_the_terminal_text_comes_from_the_same_payload():
    payload = make_payload()
    text = render_text(payload)
    assert payload["run"]["domain"] in text
    assert format(payload["scores"]["access"]["score"], "g") + "/100" in text
    assert "WHAT TO CHANGE FIRST" in text
    assert "User-agent: OAI-SearchBot" in text
