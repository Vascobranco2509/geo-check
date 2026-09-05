"""The five Access checks and the caps, against synthetic sites. Offline."""

from geo_check.checks import REGISTRY, run_all
from geo_check.checks.access_citation import citation_crawlers_allowed
from geo_check.checks.access_noindex import blocks_indexing, no_noindex
from geo_check.checks.access_pages import pages_reachable, wall_reason
from geo_check.checks.access_sitemap import sitemap_available
from geo_check.checks.access_user_fetch import user_fetch_crawlers_allowed
from geo_check.cli import collect_caps
from geo_check.models import Category, PageContext, Severity, SiteContext
from geo_check.robots import classify, load_agents
from geo_check.scoring import ACCESS_WEIGHTS, CAP_BLANKET_DISALLOW, score_category

BASE = "https://example.pt"
LONG_TEXT = "texto " * 500
PAGE_HTML = "<html><head><title>Ola</title></head><body><p>" + LONG_TEXT + "</p></body></html>"
GATE_HTML = '<html><body><form><input type="password"></form></body></html>'


def make_page(url=BASE + "/", status=200, headers=None, html=PAGE_HTML):
    return PageContext(url=url, status=status, headers=headers or {}, html=html)


def make_site(robots_txt=None, pages=None, sitemap_url=None, declared=None):
    return SiteContext(
        domain="example.pt",
        base_url=BASE,
        robots_txt=robots_txt,
        robots_status=200 if robots_txt else 404,
        robots_is_real=robots_txt is not None,
        agent_verdicts=classify(robots_txt, BASE),
        sitemap_url=sitemap_url,
        sitemap_declared_url=declared,
        llms_txt=None,
        pages=pages if pages is not None else [make_page()],
    )


def test_the_registry_covers_the_access_rubric_exactly():
    access = [check for check in REGISTRY if check.category is Category.ACCESS]
    assert {check.check_id for check in access} == set(ACCESS_WEIGHTS)
    assert sum(check.weight for check in access) == 100


def test_a_wide_open_site_scores_full_access():
    site = make_site(sitemap_url=BASE + "/sitemap.xml", declared=BASE + "/sitemap.xml")
    breakdown = score_category(run_all(site), Category.ACCESS, caps=collect_caps(site))
    assert breakdown.final_score == 100
    assert breakdown.letter == "A"
    assert site.errors == []


def test_blocking_only_training_leaves_citation_untouched():
    robots = "User-agent: GPTBot\nDisallow: /\n\nUser-agent: CCBot\nDisallow: /\n"
    result = citation_crawlers_allowed(make_site(robots))
    assert result.ratio == 1.0
    assert result.severity is Severity.OK
    assert result.fix is None


def test_the_ai_only_blackout_is_reported_at_full_severity():
    """sapo.pt in miniature: Google and Bing in, the AI assistants out."""
    robots = (
        "User-agent: OAI-SearchBot\nDisallow: /\n\n"
        "User-agent: Claude-SearchBot\nDisallow: /\n\n"
        "User-agent: PerplexityBot\nDisallow: /\n"
    )
    result = citation_crawlers_allowed(make_site(robots))
    assert result.details["ai_only_blackout"] is True
    assert result.severity is Severity.CRITICAL
    assert 0 < result.ratio < 1
    assert "invisible to ChatGPT" in result.evidence


def test_the_fix_names_every_blocked_crawler():
    result = citation_crawlers_allowed(make_site("User-agent: PerplexityBot\nDisallow: /\n"))
    assert "User-agent: PerplexityBot" in result.fix.snippet
    assert "Allow: /" in result.fix.snippet
    assert "OAI-SearchBot" not in result.fix.snippet


def test_a_block_on_an_agent_that_ignores_robots_is_called_out():
    result = user_fetch_crawlers_allowed(make_site("User-agent: Perplexity-User\nDisallow: /\n"))
    assert result.details["blocked_but_ignore_robots"] == ["Perplexity-User"]
    assert "ignoring robots.txt" in result.evidence
    # No fix offered, because nothing in robots.txt would change the outcome.
    assert result.fix is None
    # And no points lost either: the block does not stop the fetch.
    assert result.ratio == 1.0


def test_a_block_on_an_agent_that_honours_robots_gets_a_fix():
    result = user_fetch_crawlers_allowed(make_site("User-agent: Claude-User\nDisallow: /\n"))
    assert "User-agent: Claude-User" in result.fix.snippet
    # This one honours robots.txt, so the block works and costs its share.
    # This one honours robots.txt, so the block works and costs its share of
    # the bucket, whatever the bucket happens to hold today.
    total = sum(1 for a in load_agents() if a["bucket"] == "user_fetch")
    assert result.ratio == (total - 1) / total


def test_a_blanket_disallow_caps_access_at_ten():
    site = make_site("User-agent: *\nDisallow: /\n")
    breakdown = score_category(run_all(site), Category.ACCESS, caps=collect_caps(site))
    assert breakdown.final_score == CAP_BLANKET_DISALLOW
    assert breakdown.cap_applied == "User-agent: * with Disallow: /"


def test_a_cloudflare_style_file_does_not_trigger_the_blanket_cap():
    """The star group is blocked but Googlebot is named and allowed."""
    robots = "User-agent: *\nDisallow: /\n\nUser-agent: Googlebot\nAllow: /\n"
    assert collect_caps(make_site(robots)) == []


def test_all_citation_blocked_without_a_blanket_caps_at_twenty():
    # Read from the list, because the cap is about all of them and the list grows.
    tokens = [a["token"] for a in load_agents() if a["bucket"] == "citation"]
    robots = "".join("User-agent: " + t + "\nDisallow: /\n\n" for t in tokens)
    site = make_site(robots)
    caps = collect_caps(site)
    assert [reason for _, reason in caps] == ["all citation crawlers blocked"]
    assert score_category(run_all(site), Category.ACCESS, caps=caps).final_score == 20


def test_no_caps_when_some_citation_crawler_gets_through():
    assert collect_caps(make_site("User-agent: GPTBot\nDisallow: /\n")) == []


def test_a_login_form_with_no_content_reads_as_a_wall():
    assert "password field" in wall_reason(make_page(html=GATE_HTML))


def test_a_login_form_on_a_full_article_does_not():
    html = '<html><body><form><input type="password"></form><p>' + LONG_TEXT + "</p></body></html>"
    assert wall_reason(make_page(html=html)) is None


def test_an_authentication_path_reads_as_a_wall():
    assert "authentication path" in wall_reason(make_page(url=BASE + "/entrar"))


def test_a_gated_page_loses_the_points():
    result = pages_reachable(make_site(pages=[make_page(), make_page(html=GATE_HTML)]))
    assert result.ratio == 0.5
    assert result.details["heuristic"] is True


def test_a_declared_and_reachable_sitemap_scores_full():
    site = make_site(sitemap_url=BASE + "/sitemap.xml", declared=BASE + "/sitemap.xml")
    assert sitemap_available(site).ratio == 1.0


def test_an_undeclared_but_reachable_sitemap_still_scores_full_with_a_note():
    result = sitemap_available(make_site(sitemap_url=BASE + "/sitemap.xml"))
    assert result.ratio == 1.0
    assert result.severity is Severity.INFO
    assert result.fix.snippet == "Sitemap: " + BASE + "/sitemap.xml"


def test_a_declared_but_broken_sitemap_scores_zero():
    result = sitemap_available(make_site(declared=BASE + "/broken.xml"))
    assert result.ratio == 0.0
    assert "did not answer" in result.evidence


def test_no_sitemap_at_all_scores_zero():
    assert sitemap_available(make_site()).ratio == 0.0


def test_noindex_directive_parsing():
    assert blocks_indexing("noindex, nofollow") is True
    assert blocks_indexing("googlebot: noindex") is True
    assert blocks_indexing("none") is True
    assert blocks_indexing("index, follow") is False
    assert blocks_indexing("max-snippet:-1") is False


def test_a_noindex_meta_tag_costs_the_points():
    html = '<html><head><meta name="robots" content="noindex"></head><body>x</body></html>'
    result = no_noindex(make_site(pages=[make_page(html=html)]))
    assert result.ratio == 0.0
    assert result.severity is Severity.CRITICAL


def test_a_noindex_header_costs_the_points_too():
    result = no_noindex(make_site(pages=[make_page(headers={"x-robots-tag": "noindex"})]))
    assert result.ratio == 0.0
    assert "X-Robots-Tag" in result.evidence


def test_a_clean_page_keeps_the_points():
    assert no_noindex(make_site()).ratio == 1.0
