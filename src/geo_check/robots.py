"""robots.txt reading and agent classification.

Path precedence stays with protego. Do not write a custom parser, see
CLAUDE.md: Allow and Disallow ordering and wildcards are where silent bugs
live. Group *selection*, on the other hand, is done here, for a reason found
by the golden set.

protego matches a user agent by substring, because it is built for Scrapy,
where the caller passes a whole User-Agent header. We pass a bare product
token, and substring matching then produces wrong verdicts. Wikipedia has a
group named `Fetch`, aimed at a download manager, and it captured
`Meta-ExternalFetcher`. A site with `User-agent: bot` would silently block
GPTBot, Googlebot, Bingbot, PerplexityBot, OAI-SearchBot and Claude-SearchBot
in one line.

So the group is chosen here by the prefix rule the specification actually
describes, and only that group, renamed to `*`, is handed to protego. protego
still decides every path question. It simply is not asked which crawler the
rules were for.

Two things here are easy to get wrong and matter more than they look:

1. A missing robots.txt means everything is allowed. Full points, plus an
   informational note. Tools that penalise absence are simply wrong.

2. Plenty of sites answer /robots.txt with 200 and their homepage HTML. That is
   absence in disguise. Check the content type and whether the body contains
   robots syntax before trusting it.
"""

from __future__ import annotations

import json
import re
from importlib import resources

from protego import Protego

from .models import AgentVerdict, Bucket

_ROBOTS_DIRECTIVE = re.compile(
    r"^\s*(user-agent|disallow|allow|sitemap|crawl-delay)\s*:",
    re.IGNORECASE | re.MULTILINE,
)

# A group is a run of User-agent lines followed by everything else. Only Allow
# and Disallow are kept as rules, but any other directive still ends the run of
# agents, which is the part that was wrong. eventbrite.com writes
#
#     User-agent: CCBot
#     Crawl-delay: 0.7
#
#     User-agent: AhrefsBot
#     Disallow: /
#
# and treating Crawl-delay as invisible glued the two agent names into one group,
# so CCBot inherited a Disallow that was never aimed at it. Any line that is not
# a User-agent line closes the block.
_RULE_FIELDS = {"allow", "disallow"}


def load_agents() -> list[dict]:
    """Read the agent list shipped inside the package.

    Lives in the package rather than a top level data/ directory so that a
    plain `pip install geo-check` works. A wheel does not carry files from
    outside the package.
    """
    body = resources.files(__package__).joinpath("data/agents.json").read_text(encoding="utf-8")
    return json.loads(body)["agents"]


def looks_like_robots(body: str, content_type: str) -> bool:
    """Guard against a homepage served at /robots.txt.

    The body decides, the header only corroborates. sapo.pt serves a valid
    robots.txt under `Content-Type: text/html`, and a tool that treats the
    header as a veto reports that site as having no robots.txt at all, which
    is both wrong and flattering. Mislabelled text files are common enough
    that the header cannot be trusted on its own.
    """
    head = body[:500].lstrip().lower()
    if head.startswith("<!doctype") or "<html" in head:
        return False
    if "html" in content_type.lower() and "<html" in body[:5000].lower():
        return False
    return bool(_ROBOTS_DIRECTIVE.search(body))


def parse_groups(robots_txt: str) -> list[tuple[list[str], list[tuple[str, str]]]]:
    """Split robots.txt into (agent tokens, rules) groups.

    Consecutive User-agent lines share the rules that follow them. That is the
    part hand written scanners usually get wrong, so it is spelled out: a
    User-agent line only starts a new group when the previous line was a rule.
    """
    groups: list[tuple[list[str], list[tuple[str, str]]]] = []
    agents: list[str] = []
    rules: list[tuple[str, str]] = []
    collecting_agents = False

    for raw in robots_txt.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field, _, value = line.partition(":")
        field = field.strip().lower()
        value = value.strip()

        if field == "user-agent":
            if not collecting_agents:
                if agents:
                    groups.append((agents, rules))
                agents, rules = [], []
                collecting_agents = True
            agents.append(value)
        else:
            collecting_agents = False
            if agents and field in _RULE_FIELDS:
                rules.append((field, value))

    if agents:
        groups.append((agents, rules))
    return groups


def group_for(
    groups: list[tuple[list[str], list[tuple[str, str]]]], token: str
) -> tuple[str, list[tuple[str, str]]] | None:
    """The rules that govern `token`, or None when nothing mentions it.

    Two rules from RFC 9309, and the second one is easy to miss.

    A user-agent value applies when it is a prefix of the crawler token, case
    insensitively, and the most specific value wins. `*` is the fallback and
    never beats a named match.

    Then: every group declaring that winning value is merged into one. Files
    repeat an agent more often than you would think, sometimes contradicting
    themselves. contasconnosco.pt blocks CCBot at line 42 and allows it at line
    74. Taking the first group says blocked, taking the last says allowed, and
    both are wrong. Merged, `Disallow: /` and `Allow: /` tie on length, Allow
    wins, and the answer is allowed.
    """
    token_lower = token.lower()
    winning = None
    best_length = -1
    for agents, _ in groups:
        for agent in agents:
            candidate = agent.lower()
            if (
                candidate != "*"
                and token_lower.startswith(candidate)
                and len(candidate) > best_length
            ):
                winning, best_length = candidate, len(candidate)
    if winning is None:
        winning = "*"

    display = None
    merged: list[tuple[str, str]] = []
    for agents, rules in groups:
        if any(agent.lower() == winning for agent in agents):
            if display is None:
                display = next(agent for agent in agents if agent.lower() == winning)
            merged.extend(rules)

    return None if display is None else (display, merged)


MAX_RULES_SHOWN = 3


def describe_group(matched: tuple[str, list[tuple[str, str]]] | None) -> str | None:
    """One readable line naming the group and its rules, for the report.

    Ecommerce robots.txt files run to forty Disallow lines. Printing all of
    them buries the one that matters, so the list is capped and counted.
    """
    if matched is None:
        return None
    name, rules = matched
    if not rules:
        return f"User-agent: {name} (no rules)"
    shown = rules[:MAX_RULES_SHOWN]
    body = ", ".join(f"{field.capitalize()}: {value}" for field, value in shown)
    hidden = len(rules) - len(shown)
    if hidden:
        body += f", and {hidden} more"
    return f"User-agent: {name} | {body}"


def group_as_robots(rules: list[tuple[str, str]]) -> str:
    """One group, rewritten as a robots.txt that applies to everyone.

    This is what protego is given, so it answers the path question for the
    group we selected instead of the one its own substring matching would pick.
    """
    lines = ["User-agent: *"]
    lines += [f"{field.capitalize()}: {value}" for field, value in rules]
    return "\n".join(lines) + "\n"


def is_blanket_disallow(robots_txt: str) -> bool:
    """True for `User-agent: *` with `Disallow: /` and nothing narrower.

    An Allow line in the same group means content is still reachable, so it is
    not a blanket block and the 10 point cap must not fire. Cloudflare style
    files that block `*` while permitting named crawlers are handled by the
    caller, which checks the citation verdicts before applying the cap.
    """
    matched = group_for(parse_groups(robots_txt), "*")
    if matched is None:
        return False
    _, rules = matched
    if not any(field == "disallow" and value == "/" for field, value in rules):
        return False
    return not any(field == "allow" and value for field, value in rules)


def classify(robots_txt: str | None, base_url: str) -> list[AgentVerdict]:
    """One verdict per agent in the shipped agent list, with the matched rule.

    No robots.txt means every agent is allowed. The URL tested is the site
    root: phase 2 re-checks the sampled page URLs, because a site can welcome
    crawlers at / and shut them out of /blog/.
    """
    agents = load_agents()
    if robots_txt is None:
        return [
            AgentVerdict(
                token=agent["token"],
                vendor=agent["vendor"],
                bucket=Bucket(agent["bucket"]),
                allowed=True,
                matched_rule=None,
                obeys_robots=agent.get("obeys_robots", "yes"),
                ai_only=agent.get("ai_only", False),
            )
            for agent in agents
        ]

    groups = parse_groups(robots_txt)
    root = base_url.rstrip("/") + "/"
    cache: dict[str, Protego] = {}

    def allowed_for(token: str, matched) -> bool:
        if matched is None:
            return True
        body = group_as_robots(matched[1])
        parser = cache.get(body)
        if parser is None:
            parser = cache[body] = Protego.parse(body)
        return parser.can_fetch(root, "*")

    verdicts = []
    for agent in agents:
        matched = group_for(groups, agent["token"])
        verdicts.append(
            AgentVerdict(
                token=agent["token"],
                vendor=agent["vendor"],
                bucket=Bucket(agent["bucket"]),
                allowed=allowed_for(agent["token"], matched),
                matched_rule=describe_group(matched),
                obeys_robots=agent.get("obeys_robots", "yes"),
                ai_only=agent.get("ai_only", False),
            )
        )
    return verdicts


def allow_snippet(tokens: list[str]) -> str:
    """The exact robots.txt lines that unblock these agents.

    An explicit group per agent, rather than one shared group, because that is
    what a site owner can paste next to the Disallow they already have without
    having to reason about precedence.
    """
    return "\n\n".join(f"User-agent: {token}\nAllow: /" for token in tokens)


def bucket_counts(verdicts: list[AgentVerdict], bucket: Bucket) -> tuple[int, int]:
    """Returns (allowed, total) for a bucket."""
    in_bucket = [v for v in verdicts if v.bucket is bucket]
    return sum(1 for v in in_bucket if v.allowed), len(in_bucket)
