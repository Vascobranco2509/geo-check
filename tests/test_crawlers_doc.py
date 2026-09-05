"""docs/CRAWLERS.md says it is generated from agents.json. This makes that true.

Nothing generated it and nothing compared them, so the page was free to drift
behind the file it claims to be derived from, and it did: the list grew and the
page did not. A document that describes itself as generated and is not is worse
than one admitting it was written by hand, because a reader trusts it more.

What is checked here is the shape, not the prose. Every agent has a row, every
row is an agent, and the counts in the headings are the counts.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "src" / "geo_check" / "data" / "agents.json"
DOC = ROOT / "docs" / "CRAWLERS.md"
README = ROOT / "README.md"

BUCKET_HEADINGS = {
    "citation": "## Citation crawlers",
    "user_fetch": "## User fetch crawlers",
    "training": "## Training crawlers",
}

# | `Token` | [Vendor](url) | yes | What it does |, and an undocumented entry
# carries its vendor as plain text because there is no source to link to.
ROW = re.compile(r"^\| `([^`]+)` \| ([^|]+?) \| (yes|no|disputed) \|", re.MULTILINE)
LINK = re.compile(r"^\[([^\]]+)\]\(.+\)$")


def vendor_of(cell: str) -> str:
    match = LINK.match(cell.strip())
    return match.group(1) if match else cell.strip()


def agents() -> list[dict]:
    return json.loads(AGENTS.read_text(encoding="utf-8"))["agents"]


def sections() -> dict[str, str]:
    """The markdown under each bucket heading, up to the next heading."""
    body = DOC.read_text(encoding="utf-8")
    out = {}
    for bucket, heading in BUCKET_HEADINGS.items():
        start = body.index(heading)
        after = body.find("\n## ", start + len(heading))
        out[bucket] = body[start : after if after != -1 else len(body)]
    return out


def test_every_agent_has_a_row_and_every_row_is_an_agent():
    by_bucket = sections()
    for bucket, block in by_bucket.items():
        expected = {a["token"] for a in agents() if a["bucket"] == bucket}
        found = {m.group(1) for m in ROW.finditer(block)}
        assert found == expected, (
            f"{bucket}: missing from the doc {sorted(expected - found)}, "
            f"in the doc but not in the list {sorted(found - expected)}"
        )


def test_the_vendor_and_the_robots_answer_match_the_list():
    by_token = {a["token"]: a for a in agents()}
    for block in sections().values():
        for token, vendor, obeys in (m.groups() for m in ROW.finditer(block)):
            agent = by_token[token]
            assert vendor_of(vendor) == agent["vendor"], token
            assert obeys == agent.get("obeys_robots", "yes"), token


def test_the_counts_in_the_headings_are_the_counts():
    for bucket, block in sections().items():
        expected = sum(1 for a in agents() if a["bucket"] == bucket)
        stated = re.search(r"^(\d+) agents", block, re.MULTILINE)
        assert stated, f"{bucket}: no count line under the heading"
        assert int(stated.group(1)) == expected, (
            f"{bucket}: heading says {stated.group(1)}, the list has {expected}"
        )


def test_the_readme_states_the_real_number_of_agents():
    """The README sells the list, so it is the number people quote back.

    It said twenty five for as long as the list had twenty five, and would have
    gone on saying it.
    """
    expected = len(agents())
    stated = re.search(r"^(\d+) user agents", README.read_text(encoding="utf-8"), re.MULTILINE)
    assert stated, "the README no longer states an agent count in the expected form"
    assert int(stated.group(1)) == expected
