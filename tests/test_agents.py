"""The agent list is data, so it gets tested like data."""

import json
from pathlib import Path

AGENTS_PATH = Path(__file__).resolve().parents[1] / "src" / "geo_check" / "data" / "agents.json"
AGENTS = json.loads(AGENTS_PATH.read_text(encoding="utf-8"))


def test_every_agent_has_the_required_fields():
    for agent in AGENTS["agents"]:
        assert agent["token"], agent
        assert agent["vendor"], agent
        assert agent["bucket"] in {"citation", "user_fetch", "training"}, agent
        assert agent["obeys_robots"] in {"yes", "no", "disputed"}, agent
        assert agent["docs"].startswith("http"), agent


def test_tokens_are_unique():
    tokens = [a["token"] for a in AGENTS["agents"]]
    assert len(tokens) == len(set(tokens))


def test_each_bucket_is_populated():
    buckets = {a["bucket"] for a in AGENTS["agents"]}
    assert buckets == {"citation", "user_fetch", "training"}


def test_the_file_ships_inside_the_package():
    """A wheel does not carry files from outside the package directory."""
    from geo_check.robots import load_agents

    assert len(load_agents()) == len(AGENTS["agents"])
