"""The golden set. Thirty hard sites, replayed from recorded responses.

These require 100 percent accuracy. Every expectation in data/golden_30.yaml was
checked by hand against the recorded robots.txt: each blocked agent was traced
either to a group that names it or to the star group it falls back to.

If one of these fails, read the robots.txt in the fixture before touching the
expectation. The whole point of this file is that it is harder to change than
the code.
"""

from pathlib import Path

import pytest
import yaml

from geo_check.checks import run_all
from geo_check.cli import collect_caps
from geo_check.fixtures import Replayer, available, load
from geo_check.models import Bucket, Category
from geo_check.robots import bucket_counts
from geo_check.scoring import score_category, training_posture
from geo_check.site import SiteUnavailable, build_site

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "golden"
GOLDEN = yaml.safe_load((ROOT / "data" / "golden_30.yaml").read_text(encoding="utf-8"))
BY_DOMAIN = {entry["domain"]: entry for entry in GOLDEN}


def audit(domain):
    """Replay one recorded site and return what the tool concludes."""
    site = build_site(domain, pages=5, fetcher=Replayer(load(FIXTURES, domain)["responses"]))
    results = run_all(site)
    access = score_category(results, Category.ACCESS, caps=collect_caps(site))
    citation_allowed, citation_total = bucket_counts(site.agent_verdicts, Bucket.CITATION)
    fetch_allowed, fetch_total = bucket_counts(site.agent_verdicts, Bucket.USER_FETCH)
    training_allowed, training_total = bucket_counts(site.agent_verdicts, Bucket.TRAINING)
    return {
        "outcome": "scored",
        "robots_is_real": site.robots_is_real,
        "citation_allowed": citation_allowed,
        "citation_total": citation_total,
        "user_fetch_allowed": fetch_allowed,
        "user_fetch_total": fetch_total,
        "training_posture": training_posture(training_allowed, training_total),
        "llms_txt": bool((site.llms_txt or "").strip()),
        "sitemap_reachable": site.sitemap_url is not None,
        "access_score": round(access.final_score, 2),
        "access_cap": access.cap_applied,
    }


def test_every_golden_entry_has_a_fixture_and_a_reason():
    assert len(GOLDEN) == 30
    on_disk = set(available(FIXTURES))
    assert set(BY_DOMAIN) == on_disk, set(BY_DOMAIN) ^ on_disk
    for entry in GOLDEN:
        assert entry["reason"].strip(), entry["domain"]


@pytest.mark.parametrize("domain", sorted(BY_DOMAIN))
def test_golden(domain):
    expected = BY_DOMAIN[domain]["expected"]
    if expected["outcome"] == "aborted":
        with pytest.raises(SiteUnavailable) as caught:
            build_site(domain, pages=5, fetcher=Replayer(load(FIXTURES, domain)["responses"]))
        assert caught.value.reason == expected["abort_reason"]
        return
    assert audit(domain) == expected


def test_the_set_actually_covers_the_hard_shapes():
    """A golden set of thirty easy sites would pass and prove nothing."""
    scored = [e["expected"] for e in GOLDEN if e["expected"]["outcome"] == "scored"]
    assert sum(1 for e in scored if not e["robots_is_real"]) >= 4, "no absent or fake robots.txt"
    assert any(e["access_cap"] for e in scored), "no capped site"
    assert any(e["citation_allowed"] == 0 for e in scored), "nothing fully blocked"
    assert any(e["citation_allowed"] < e["citation_total"] for e in scored), "no partial block"
    assert any(e["training_posture"] == "open" for e in scored)
    assert any(e["training_posture"] == "partial" for e in scored)
    assert any(e["training_posture"] == "closed" for e in scored)
    assert any(e["llms_txt"] for e in scored), "no llms.txt in the set"
    assert sum(1 for e in GOLDEN if e["expected"]["outcome"] == "aborted") >= 3


def test_blocking_training_never_costs_access_points():
    """The most opinionated call in the project, checked against real sites."""
    for entry in GOLDEN:
        expected = entry["expected"]
        if expected["outcome"] != "scored":
            continue
        untouched = (
            expected["citation_allowed"] == expected["citation_total"]
            and expected["user_fetch_allowed"] == expected["user_fetch_total"]
        )
        if untouched and expected["training_posture"] != "open":
            assert expected["access_score"] >= 90, entry["domain"]
