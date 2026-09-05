"""robots.txt parsing and agent classification. Offline, hand written inputs.

Every fixture here is a robots.txt shape seen in the wild. The one that matters
most is `TRAINING_ONLY_BLOCK`: a site that blocked the training crawlers and
kept every citation crawler. That is the correct configuration for a publisher
who does not want to feed model training, and a tool that marks it down is
giving bad advice.
"""

from geo_check.models import Bucket
from geo_check.robots import (
    bucket_counts,
    classify,
    describe_group,
    group_for,
    is_blanket_disallow,
    load_agents,
    looks_like_robots,
    parse_groups,
)

BASE = "https://example.pt"

BLANKET = "User-agent: *\nDisallow: /\n"
BLANKET_WITH_ALLOW = "User-agent: *\nDisallow: /\nAllow: /publico/\n"
CLOUDFLARE_STYLE = "User-agent: *\nDisallow: /\n\nUser-agent: Googlebot\nAllow: /\n"
SHARED_GROUP = "User-agent: GPTBot\nUser-agent: PerplexityBot\nDisallow: /\n"
TRAINING_ONLY_BLOCK = (
    "User-agent: GPTBot\nDisallow: /\n\n"
    "User-agent: CCBot\nDisallow: /\n\n"
    "User-agent: Google-Extended\nDisallow: /\n\n"
    "User-agent: *\nDisallow: /wp-admin/\n"
)
WIDE_OPEN = "User-agent: *\nDisallow:\nSitemap: https://example.pt/sitemap.xml\n"


def _size(bucket):
    """How many agents that bucket holds, read from the list rather than typed.

    These assertions used to spell the sizes out, so adding a crawler broke
    thirteen tests that had no opinion about crawlers. What they mean is all of
    them, or none of them.
    """
    return sum(1 for a in load_agents() if a["bucket"] == bucket.value)


def _all(bucket):
    return (_size(bucket), _size(bucket))


def _none(bucket):
    return (0, _size(bucket))


def _allowed(robots_txt, bucket):
    return bucket_counts(classify(robots_txt, BASE), bucket)


def test_no_robots_txt_allows_everything():
    verdicts = classify(None, BASE)
    assert all(v.allowed for v in verdicts)
    assert all(v.matched_rule is None for v in verdicts)


def test_blanket_disallow_blocks_every_bucket():
    assert is_blanket_disallow(BLANKET) is True
    assert _allowed(BLANKET, Bucket.CITATION) == _none(Bucket.CITATION)
    assert _allowed(BLANKET, Bucket.USER_FETCH) == _none(Bucket.USER_FETCH)


def test_a_narrower_allow_is_not_a_blanket_disallow():
    """The 10 point cap must not fire when some content is still reachable."""
    assert is_blanket_disallow(BLANKET_WITH_ALLOW) is False


def test_cloudflare_style_leaves_the_named_crawler_allowed():
    """`*` is blocked but Googlebot has its own group, so it still gets in."""
    verdicts = classify(CLOUDFLARE_STYLE, BASE)
    googlebot = next(v for v in verdicts if v.token == "Googlebot")
    perplexity = next(v for v in verdicts if v.token == "PerplexityBot")
    assert googlebot.allowed is True
    assert perplexity.allowed is False
    assert is_blanket_disallow(CLOUDFLARE_STYLE) is True


def test_consecutive_user_agent_lines_share_the_rules():
    groups = parse_groups(SHARED_GROUP)
    assert groups == [(["GPTBot", "PerplexityBot"], [("disallow", "/")])]
    verdicts = classify(SHARED_GROUP, BASE)
    blocked = {v.token for v in verdicts if not v.allowed}
    assert blocked == {"GPTBot", "PerplexityBot"}


def test_blocking_training_does_not_touch_citation():
    """The whole point of the project, in one assertion."""
    assert _allowed(TRAINING_ONLY_BLOCK, Bucket.CITATION) == _all(Bucket.CITATION)
    assert _allowed(TRAINING_ONLY_BLOCK, Bucket.USER_FETCH) == _all(Bucket.USER_FETCH)
    training_allowed, training_total = _allowed(TRAINING_ONLY_BLOCK, Bucket.TRAINING)
    assert training_allowed < training_total


def test_wide_open_allows_everything():
    verdicts = classify(WIDE_OPEN, BASE)
    assert all(v.allowed for v in verdicts)
    assert is_blanket_disallow(WIDE_OPEN) is False


def test_matched_rule_names_the_group_and_keeps_its_casing():
    groups = parse_groups(TRAINING_ONLY_BLOCK)
    assert describe_group(group_for(groups, "GPTBot")) == "User-agent: GPTBot | Disallow: /"
    assert describe_group(group_for(groups, "OAI-SearchBot")) == (
        "User-agent: * | Disallow: /wp-admin/"
    )


def test_user_agent_matching_is_case_insensitive():
    verdicts = classify("user-agent: gptbot\ndisallow: /\n", BASE)
    gptbot = next(v for v in verdicts if v.token == "GPTBot")
    assert gptbot.allowed is False


def test_comments_are_ignored():
    robots = "# block the training crawlers\nUser-agent: GPTBot  # openai\nDisallow: /\n"
    groups = parse_groups(robots)
    assert groups == [(["GPTBot"], [("disallow", "/")])]


def test_wildcard_paths_do_not_block_the_root():
    robots = "User-agent: *\nDisallow: /*.pdf$\nDisallow: /search?*\n"
    assert _allowed(robots, Bucket.CITATION) == _all(Bucket.CITATION)
    assert is_blanket_disallow(robots) is False


def test_allow_wins_over_a_disallow_of_the_same_path():
    robots = "User-agent: *\nDisallow: /\nAllow: /\n"
    assert is_blanket_disallow(robots) is False
    assert _allowed(robots, Bucket.CITATION) == _all(Bucket.CITATION)


def test_obeys_robots_is_carried_into_the_verdict():
    verdicts = classify(BLANKET, BASE)
    perplexity_user = next(v for v in verdicts if v.token == "Perplexity-User")
    claude_user = next(v for v in verdicts if v.token == "Claude-User")
    assert perplexity_user.obeys_robots == "no"
    assert perplexity_user.block_is_effective is False
    assert claude_user.block_is_effective is True


def test_a_homepage_served_at_robots_txt_is_not_robots_txt():
    assert looks_like_robots("<!DOCTYPE html><html><body>Ola", "text/html") is False
    assert looks_like_robots("<html lang='pt'>", "text/plain") is False
    assert looks_like_robots("User-agent: *\nDisallow: /x", "text/plain") is True


def test_a_body_with_no_directives_is_not_robots_txt():
    assert looks_like_robots("nothing to see here", "text/plain") is False


def test_a_valid_robots_txt_mislabelled_as_html_is_still_robots_txt():
    """sapo.pt serves this exact shape. Trusting the header loses the file."""
    body = "User-agent: *\n\nSitemap: https://sapo.pt/sitemap.xml\nDisallow: /pesquisa\n"
    assert looks_like_robots(body, "text/html; charset=utf-8") is True


def test_a_real_html_page_labelled_text_plain_is_still_not_robots_txt():
    body = "<!DOCTYPE HTML><HTML><HEAD><TITLE>403 ERROR</TITLE></HEAD></HTML>"
    assert looks_like_robots(body, "text/plain") is False


# --- user agent matching ---------------------------------------------------
#
# protego matches user agents by substring, because Scrapy hands it a whole
# User-Agent header. We hand it a bare product token, so the group is selected
# here and only that group reaches protego. These are the cases that found it.


def test_a_group_named_bot_does_not_capture_every_crawler():
    """One line would otherwise silently block six citation crawlers."""
    robots = "User-agent: bot\nDisallow: /\n\nUser-agent: *\nAllow: /\n"
    assert _allowed(robots, Bucket.CITATION) == _all(Bucket.CITATION)
    assert _allowed(robots, Bucket.USER_FETCH) == _all(Bucket.USER_FETCH)


def test_a_group_named_fetch_does_not_capture_meta_externalfetcher():
    """Wikipedia has exactly this group, aimed at a download manager."""
    robots = "User-agent: Fetch\nDisallow: /\n\nUser-agent: *\nAllow: /\n"
    verdicts = classify(robots, BASE)
    meta = next(v for v in verdicts if v.token == "Meta-ExternalFetcher")
    assert meta.allowed is True
    assert meta.matched_rule == "User-agent: * | Allow: /"


def test_a_prefix_of_the_token_still_matches():
    """Google matches Googlebot and Google-Extended, which is the real rule."""
    robots = "User-agent: Google\nDisallow: /\n\nUser-agent: *\nAllow: /\n"
    verdicts = {v.token: v.allowed for v in classify(robots, BASE)}
    assert verdicts["Googlebot"] is False
    assert verdicts["Google-Extended"] is False
    assert verdicts["Bingbot"] is True


def test_the_longest_matching_group_wins():
    robots = (
        "User-agent: Google\nDisallow: /\n\n"
        "User-agent: Googlebot\nAllow: /\n\n"
        "User-agent: *\nAllow: /\n"
    )
    verdicts = {v.token: v.allowed for v in classify(robots, BASE)}
    assert verdicts["Googlebot"] is True
    assert verdicts["Google-Extended"] is False


def test_path_precedence_is_still_protego_s_job():
    """The group is ours, every path question stays with the library."""
    robots = "User-agent: *\nDisallow: /\nAllow: /publico/\n"
    verdicts = classify(robots, BASE)
    assert all(not v.allowed for v in verdicts)
    # The narrower Allow still wins on its own path, decided by protego.
    assert classify(robots, BASE + "/publico")[0].allowed is True
    from geo_check.robots import group_as_robots

    assert group_as_robots([("disallow", "/"), ("allow", "/x/")]) == (
        "User-agent: *\nDisallow: /\nAllow: /x/\n"
    )


def test_groups_declaring_the_same_agent_are_merged():
    """RFC 9309 says merge, and real files contradict themselves.

    contasconnosco.pt blocks CCBot at line 42 and allows it at line 74. Taking
    the first group says blocked, taking the last says allowed, and both are
    wrong. Merged, the two rules tie on length and Allow wins.
    """
    robots = (
        "User-agent: CCBot\nDisallow: /\n\n"
        "User-agent: *\nAllow: /\n\n"
        "User-agent: GPTBot\nUser-agent: CCBot\nAllow: /\n"
    )
    verdicts = {v.token: v.allowed for v in classify(robots, BASE)}
    assert verdicts["CCBot"] is True
    assert verdicts["GPTBot"] is True


def test_merging_does_not_reach_across_different_agents():
    """Only the winning value is merged. Google and Googlebot stay separate."""
    robots = "User-agent: Google\nAllow: /\n\nUser-agent: Googlebot\nDisallow: /\n"
    verdicts = {v.token: v.allowed for v in classify(robots, BASE)}
    assert verdicts["Googlebot"] is False
    assert verdicts["Google-Extended"] is True


def test_repeated_star_groups_are_merged_too():
    robots = "User-agent: *\nDisallow: /\n\nUser-agent: *\nAllow: /\n"
    assert _allowed(robots, Bucket.CITATION) == _all(Bucket.CITATION)


def test_a_crawl_delay_line_closes_the_agent_block():
    """eventbrite.com writes exactly this, and it cost CCBot a Disallow.

    Only Allow and Disallow become rules, but every other directive still ends
    the run of user-agent lines. Treating Crawl-delay as invisible glued two
    agents into one group and gave the first the second's rules.
    """
    robots = (
        "User-agent: CCBot\nCrawl-delay: 0.7\n\n"
        "User-agent: AhrefsBot\nDisallow: /\n\n"
        "User-agent: *\nAllow: /\n"
    )
    groups = parse_groups(robots)
    assert (["CCBot"], []) in groups
    assert (["AhrefsBot"], [("disallow", "/")]) in groups
    verdicts = {v.token: v.allowed for v in classify(robots, BASE)}
    assert verdicts["CCBot"] is True


def test_a_sitemap_line_between_groups_closes_the_block_too():
    robots = (
        "User-agent: GPTBot\nSitemap: https://example.pt/sitemap.xml\n\n"
        "User-agent: PerplexityBot\nDisallow: /\n"
    )
    verdicts = {v.token: v.allowed for v in classify(robots, BASE)}
    assert verdicts["GPTBot"] is True
    assert verdicts["PerplexityBot"] is False


def test_consecutive_agents_still_share_rules_across_the_change():
    """The fix must not break the case that motivated the parser originally."""
    groups = parse_groups("User-agent: GPTBot\nUser-agent: CCBot\nDisallow: /\n")
    assert groups == [(["GPTBot", "CCBot"], [("disallow", "/")])]
