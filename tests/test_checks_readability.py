"""The eight Readability checks, against hand written HTML. Offline."""

from geo_check.checks import REGISTRY
from geo_check.checks.readability_answers import DETECTORS, answer_shaped_content
from geo_check.checks.readability_author_dates import author_and_dates
from geo_check.checks.readability_canonical import canonical
from geo_check.checks.readability_headings import heading_structure, score_page
from geo_check.checks.readability_jsonld import jsonld_valid
from geo_check.checks.readability_llms_txt import llms_txt
from geo_check.checks.readability_raw_html import raw_html_content
from geo_check.checks.readability_title import title_and_description
from geo_check.models import Category, PageContext, Severity, SiteContext
from geo_check.scoring import READABILITY_WEIGHTS

BASE = "https://example.pt"
PROSE = "palavra " * 600

ARTICLE_LD = (
    '<script type="application/ld+json">'
    '{"@context":"https://schema.org","@type":"NewsArticle","headline":"h"}'
    "</script>"
)


def page(html, url=BASE + "/", status=200, headers=None):
    return PageContext(url=url, status=status, headers=headers or {}, html=html)


def site(pages, llms=None):
    return SiteContext(
        domain="example.pt",
        base_url=BASE,
        robots_txt=None,
        robots_status=404,
        robots_is_real=False,
        agent_verdicts=[],
        sitemap_url=None,
        sitemap_declared_url=None,
        llms_txt=llms,
        pages=pages,
    )


def document(body, head=""):
    return "<html><head>" + head + "</head><body>" + body + "</body></html>"


def test_the_registry_covers_the_readability_rubric_exactly():
    checks = [c for c in REGISTRY if c.category is Category.READABILITY]
    assert {c.check_id for c in checks} == set(READABILITY_WEIGHTS)
    assert sum(c.weight for c in checks) == 100


def test_only_pages_that_answered_200_are_read():
    """A 404 in the sitemap is charged to pages_reachable, not twice."""
    context = site([page(document("<p>" + PROSE + "</p>")), page("", status=404)])
    assert len(context.readable_pages) == 1


def test_an_empty_shell_scores_nothing():
    result = raw_html_content(site([page(document('<div id="root"></div>'))]))
    assert result.ratio == 0.0
    assert result.severity is Severity.CRITICAL
    assert result.details["heuristic"] is True


def test_a_script_heavy_page_is_marked_down_even_with_some_text():
    """jn.pt in miniature: 1463 characters of text against 357000 of script."""
    body = "<p>" + ("texto " * 120) + "</p><script>" + ("x=1;" * 60000) + "</script>"
    result = raw_html_content(site([page(document(body))]))
    assert result.ratio == 0.25
    assert "to 1" in result.evidence


def test_a_thin_page_keeps_half():
    result = raw_html_content(site([page(document("<p>" + ("texto " * 150) + "</p>"))]))
    assert result.ratio == 0.5


def test_a_full_page_keeps_everything():
    result = raw_html_content(site([page(document("<p>" + PROSE + "</p>"))]))
    assert result.ratio == 1.0
    assert result.severity is Severity.OK


def test_a_recognised_type_scores_full():
    result = jsonld_valid(site([page(document("<p>x</p>", head=ARTICLE_LD))]))
    assert result.ratio == 1.0
    assert result.severity is Severity.OK


def test_a_type_inside_an_at_graph_is_found():
    head = (
        '<script type="application/ld+json">'
        '{"@graph":[{"@type":"WebSite"},{"@type":"Article","headline":"h"}]}'
        "</script>"
    )
    assert jsonld_valid(site([page(document("<p>x</p>", head=head))])).ratio == 1.0


def test_an_unrecognised_type_scores_nothing_and_is_named():
    head = '<script type="application/ld+json">{"@type":"MadeUpThing"}</script>'
    result = jsonld_valid(site([page(document("<p>x</p>", head=head))]))
    assert result.ratio == 0.0
    assert "madeupthing" in result.evidence.lower()


def test_broken_json_is_counted_and_reported():
    head = ARTICLE_LD + '<script type="application/ld+json">{ nope </script>'
    result = jsonld_valid(site([page(document("<p>x</p>", head=head))]))
    assert result.ratio == 1.0
    assert result.details["broken_blocks"] == 1
    assert result.severity is Severity.WARNING


def test_one_h1_and_an_orderly_descent_scores_full():
    body = "<h1>a</h1><h2>b</h2><h3>c</h3><h2>d</h2>"
    assert score_page(page(document(body)))[0] == 1.0


def test_a_skipped_level_costs_the_descent_share():
    assert score_page(page(document("<h1>a</h1><h3>c</h3>")))[0] == 0.6


def test_several_h1_elements_cost_the_larger_share():
    assert score_page(page(document("<h1>a</h1><h1>b</h1><h2>c</h2>")))[0] == 0.4


def test_no_h1_scores_nothing():
    score, note = score_page(page(document("<h2>a</h2><h3>b</h3>")))
    assert (score, note) == (0.0, "no h1")


def test_the_heading_check_averages_across_the_sample():
    good = page(document("<h1>a</h1><h2>b</h2>"))
    bad = page(document("<h2>a</h2>"), url=BASE + "/dois")
    assert heading_structure(site([good, bad])).ratio == 0.5


GOOD_HEAD = (
    "<title>Um titulo com tamanho razoavel</title>"
    '<meta name="description" content="descricao suficiente para passar o minimo'
    ' de cinquenta caracteres exigidos">'
)


def test_a_good_title_and_description_score_full():
    result = title_and_description(site([page(document("<p>x</p>", head=GOOD_HEAD))]))
    assert result.ratio == 1.0
    assert result.severity is Severity.OK


def test_a_missing_title_is_named_in_the_evidence():
    result = title_and_description(site([page(document("<p>x</p>"))]))
    assert result.ratio == 0.0
    assert "no title" in result.evidence


def test_a_title_outside_the_range_earns_half_and_says_so():
    head = "<title>curto</title>"
    result = title_and_description(site([page(document("<p>x</p>", head=head))]))
    assert result.details["titles_outside_range"] == 1
    assert "fall outside" in result.evidence


def test_repeated_titles_cost_the_uniqueness_share():
    one = page(document("<p>x</p>", head=GOOD_HEAD))
    two = page(document("<p>x</p>", head=GOOD_HEAD), url=BASE + "/dois")
    result = title_and_description(site([one, two]))
    assert result.details["titles_unique"] is False
    assert result.ratio == 0.8


def test_meta_tags_identify_an_author_and_a_date():
    head = (
        '<meta name="author" content="Ana">'
        '<meta property="article:published_time" content="2026-08-30">'
    )
    assert author_and_dates(site([page(document("<p>x</p>", head=head))])).ratio == 1.0


def test_json_ld_identifies_an_author_and_a_date():
    head = (
        '<script type="application/ld+json">'
        '{"@type":"Article","author":{"@type":"Person","name":"Ana"},'
        '"datePublished":"2026-08-30"}'
        "</script>"
    )
    assert author_and_dates(site([page(document("<p>x</p>", head=head))])).ratio == 1.0


def test_a_time_element_counts_as_a_date():
    body = '<time datetime="2026-08-30">30 de agosto</time>'
    result = author_and_dates(site([page(document(body))]))
    assert result.ratio == 0.5
    assert result.details["with_date"] == 1


def test_nothing_identifiable_scores_nothing():
    assert author_and_dates(site([page(document("<p>x</p>"))])).ratio == 0.0


def test_a_self_referencing_canonical_scores_full():
    head = '<link rel="canonical" href="https://example.pt/">'
    assert canonical(site([page(document("<p>x</p>", head=head))])).ratio == 1.0


def test_a_relative_canonical_is_resolved_against_the_page():
    head = '<link rel="canonical" href="/pagina">'
    assert canonical(site([page(document("<p>x</p>", head=head))])).ratio == 1.0


def test_a_canonical_on_another_host_is_a_fault():
    head = '<link rel="canonical" href="https://staging.example.com/">'
    result = canonical(site([page(document("<p>x</p>", head=head))]))
    assert result.ratio == 0.0
    assert "another host" in result.evidence


def test_a_missing_canonical_is_a_fault():
    assert canonical(site([page(document("<p>x</p>"))])).ratio == 0.0


def test_a_real_llms_txt_scores_full():
    body = "# Exemplo\n\n" + ("- [Pagina](https://example.pt/p): descricao\n" * 5)
    result = llms_txt(site([page(document("<p>x</p>"))], llms=body))
    assert result.ratio == 1.0
    assert result.severity is Severity.OK


def test_a_placeholder_llms_txt_scores_nothing():
    result = llms_txt(site([page(document("<p>x</p>"))], llms="# TODO"))
    assert result.ratio == 0.0
    assert "placeholder" in result.evidence


def test_a_missing_llms_txt_is_informational_not_a_warning():
    result = llms_txt(site([page(document("<p>x</p>"))]))
    assert result.ratio == 0.0
    assert result.severity is Severity.INFO


def test_each_extractable_shape_is_detected():
    cases = {
        "numbered steps": "<ol><li>a</li><li>b</li><li>c</li></ol>",
        "comparison table": "<table><tr><th>a</th></tr><tr><td>b</td></tr><tr><td>c</td></tr></table>",
        "question and answer block": "<h2>O que e isto?</h2><h2>Como funciona?</h2>",
        "definition list": "<dl><dt>termo</dt><dd>definicao</dd></dl>",
        "attributed quote": "<blockquote><p>x</p><cite>Ana</cite></blockquote>",
        "summary box": "<h2>Em resumo</h2><ul><li>a</li></ul>",
    }
    assert set(cases) == set(DETECTORS)
    for name, body in cases.items():
        found = answer_shaped_content(site([page(document(body))])).details["found"]
        assert found == [name], (name, found)


def test_three_shapes_earn_the_full_five_points():
    body = (
        "<ol><li>a</li><li>b</li><li>c</li></ol>"
        "<dl><dt>t</dt><dd>d</dd></dl>"
        "<blockquote><p>x</p><cite>Ana</cite></blockquote>"
    )
    assert answer_shaped_content(site([page(document(body))])).ratio == 1.0


def test_continuous_prose_finds_no_extractable_shape():
    result = answer_shaped_content(site([page(document("<p>" + PROSE + "</p>"))]))
    assert result.ratio == 0.0
    assert result.details["structural_only"] is True


# --- citable blocks --------------------------------------------------------
#
# The idea is borrowed from zubair-trabzada/geo-seo-claude (MIT); the thresholds
# are not. Theirs score blocks against 134 to 167 words, and measuring 12301
# blocks across 868 corpus pages showed that band covers 2.6 percent of what
# actually exists. What separates is how much of a page sits in its largest
# block. Numbers in data/block_calibration.csv.


def sectioned(sections: int, words: int) -> str:
    body = "".join(
        "<h2>seccao " + str(i) + "</h2><p>" + ("palavra " * words) + "</p>" for i in range(sections)
    )
    return document(body)


def test_one_undivided_wall_scores_nothing_on_the_block_half():
    result = answer_shaped_content(
        site([page(document("<h1>t</h1><p>" + "palavra " * 800 + "</p>"))])
    )
    assert result.details["block_share"] == 0.0
    assert result.ratio == 0.0
    assert "one undivided block" in result.evidence


def test_evenly_sectioned_prose_scores_full_on_the_block_half():
    result = answer_shaped_content(site([page(sectioned(6, 120))]))
    assert result.details["block_share"] == 1.0


def test_shapes_alone_earn_six_tenths_of_the_check():
    """Three shapes but one wall of prose behind them."""
    body = (
        "<h1>t</h1>"
        "<ol><li>a</li><li>b</li><li>c</li></ol>"
        "<dl><dt>t</dt><dd>d</dd></dl>"
        "<blockquote><p>x</p><cite>Ana</cite></blockquote>"
        "<p>" + ("palavra " * 900) + "</p>"
    )
    result = answer_shaped_content(site([page(document(body))]))
    assert result.details["shape_share"] == 1.0
    assert result.details["block_share"] == 0.0
    assert round(result.ratio, 3) == 0.6


def test_sections_alone_earn_four_tenths_of_the_check():
    result = answer_shaped_content(site([page(sectioned(6, 120))]))
    assert result.details["shape_share"] == 0.0
    assert round(result.ratio, 3) == 0.4


def test_a_page_too_short_to_have_sections_is_not_penalised():
    """Shortness is raw_html_content's business, not this check's."""
    result = answer_shaped_content(
        site([page(document("<h1>t</h1><p>" + "palavra " * 50 + "</p>"))])
    )
    assert result.details["block_share"] == 1.0


def test_the_wall_is_named_so_someone_can_go_and_fix_it():
    wall = page(document("<h1>t</h1><p>" + "palavra " * 800 + "</p>"), url=BASE + "/muro")
    result = answer_shaped_content(site([page(sectioned(6, 120)), wall]))
    assert result.details["pages_that_are_one_block"] == [BASE + "/muro"]
    assert result.details["block_share"] == 0.5
