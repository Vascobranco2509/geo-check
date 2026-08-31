"""The Content-Signal directive, read the way sites actually write it.

The key set in these tests comes from the corpus rather than from the draft
specification. Of 906 sites, 47 declare signals and 8 publish the explanatory
terms without ever declaring one, which is a different thing and is reported
differently.
"""

from geo_check.content_signals import parse

CLOUDFLARE_TERMS = """# As a condition of accessing this website, you agree to abide by the following
# content signals:
#
# (a)  If a content-signal = yes, you may collect content for the corresponding
#      use.
"""


def test_no_directive_is_not_a_finding():
    assert parse(None) is None
    assert parse("User-agent: *\nAllow: /\n") is None


def test_the_shape_fifteen_sites_send():
    signals = parse("Content-Signal: search=yes,ai-train=no,use=reference\n")
    assert signals is not None
    assert signals.declared == {"search": "yes", "ai-train": "no", "use": "reference"}
    assert signals.unknown_keys == []
    assert "allows appearing in AI search results" in signals.summary()
    assert "refuses being used to train a model" in signals.summary()


def test_spaces_after_commas_are_the_common_form():
    signals = parse("Content-Signal: ai-train=no, search=yes, ai-input=no\n")
    assert signals is not None
    assert signals.declared["ai-input"] == "no"


def test_the_draft_keys_are_accepted_even_though_no_site_sends_them():
    """The draft is still moving. A site following it is not making a mistake."""
    signals = parse("Content-Signal: ai-retrieval=yes, ai-personalization=no\n")
    assert signals is not None
    assert signals.unknown_keys == []


def test_an_unrecognised_key_is_reported_rather_than_dropped():
    signals = parse("Content-Signal: search=yes, ai-hovercraft=no\n")
    assert signals is not None
    assert signals.declared == {"search": "yes"}
    assert signals.unknown_keys == ["ai-hovercraft"]


def test_terms_without_a_signal_are_their_own_state():
    """Eight sites publish the whole legal block and never declare anything.

    By the wording of that block, doing so grants and restricts nothing, so
    reporting it as absent would hide a decision the owner probably did not
    realise they were making.
    """
    signals = parse(CLOUDFLARE_TERMS)
    assert signals is not None
    assert signals.boilerplate_only is True
    assert signals.declared == {}
    assert "declares no signal" in signals.summary()


def test_a_repeated_key_takes_the_later_value():
    signals = parse("Content-Signal: ai-train=yes\nContent-Signal: ai-train=no\n")
    assert signals is not None
    assert signals.declared["ai-train"] == "no"


def test_the_directive_is_case_insensitive_like_the_rest_of_robots_txt():
    assert parse("CONTENT-SIGNAL: Search=YES\n").declared == {"search": "yes"}
