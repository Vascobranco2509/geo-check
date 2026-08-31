"""Core data contracts.

Every check in this project follows the same shape. Adding a GEO or SEO check
later means writing one file that returns a CheckResult and registering it. Do
not add a plugin system or entry points, see CLAUDE.md.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from functools import cached_property
from typing import Any, Protocol

from bs4 import BeautifulSoup


class Category(str, Enum):
    ACCESS = "access"
    READABILITY = "readability"


class Bucket(str, Enum):
    CITATION = "citation"
    USER_FETCH = "user_fetch"
    TRAINING = "training"


class Severity(str, Enum):
    OK = "ok"
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Fix:
    """A concrete remediation. Never a vague suggestion."""

    summary: str
    # Exact lines to paste, for example robots.txt directives. Empty when the
    # fix is not a copy and paste one.
    snippet: str = ""
    docs_url: str = ""


@dataclass
class CheckResult:
    check_id: str
    category: Category
    # Fraction of the check weight earned, 0.0 to 1.0.
    ratio: float
    severity: Severity
    title: str
    # Human readable statement of what was actually observed. Always concrete:
    # a URL, a header value, a robots.txt line. Never "the site has issues".
    evidence: str
    fix: Fix | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= self.ratio <= 1.0:
            raise ValueError(f"{self.check_id}: ratio must be between 0 and 1")


@dataclass
class AgentVerdict:
    token: str
    vendor: str
    bucket: Bucket
    allowed: bool
    # The robots.txt line responsible for the verdict, when there is one.
    matched_rule: str | None = None
    # Whether the vendor documents this agent as honouring robots.txt: "yes",
    # "no" or "disputed". Perplexity-User and ChatGPT-User are documented as
    # ignoring it, so a Disallow aimed at them changes nothing. The report says
    # so instead of pretending the block worked.
    obeys_robots: str = "yes"
    # True for citation crawlers that exist only to feed AI answers. Googlebot
    # and Bingbot also carry classic search, so blocking those is a bigger and
    # different story than losing AI visibility.
    ai_only: bool = False

    @property
    def block_is_effective(self) -> bool:
        """False when a Disallow for this agent is documented as ignored."""
        return self.obeys_robots == "yes"


def _flatten_jsonld(node) -> list[dict]:
    """Pull every typed object out, following @graph, which most CMS output uses."""
    found: list[dict] = []
    if isinstance(node, list):
        for item in node:
            found.extend(_flatten_jsonld(item))
    elif isinstance(node, dict):
        graph = node.get("@graph")
        if isinstance(graph, list):
            found.extend(_flatten_jsonld(graph))
        if node.get("@type"):
            found.append(node)
    return found


@dataclass
class PageContext:
    """One sampled page, already fetched."""

    url: str
    status: int
    headers: dict[str, str]
    html: str

    @cached_property
    def soup(self) -> BeautifulSoup:
        """Parsed once per page, not once per check."""
        return BeautifulSoup(self.html, "lxml")

    @cached_property
    def text(self) -> str:
        """Visible text, with script and style stripped."""
        soup = BeautifulSoup(self.html, "lxml")
        for tag in soup(["script", "style", "noscript", "template"]):
            tag.decompose()
        return " ".join(soup.get_text(" ", strip=True).split())

    @cached_property
    def _jsonld(self) -> tuple[list[dict], int]:
        """Every JSON-LD object on the page, and how many blocks failed to parse.

        A block that is not valid JSON is counted rather than discarded. It is
        one of the most common structured data faults and the site owner cannot
        fix what the report does not mention.
        """
        blocks: list[dict] = []
        broken = 0
        for tag in self.soup.find_all("script"):
            declared = (tag.get("type") or "").lower()
            if "ld+json" not in declared:
                continue
            raw = tag.string or tag.get_text() or ""
            if not raw.strip():
                continue
            try:
                blocks.extend(_flatten_jsonld(json.loads(raw)))
            except (ValueError, TypeError):
                broken += 1
        return blocks, broken

    @property
    def jsonld(self) -> list[dict]:
        return self._jsonld[0]

    @property
    def broken_jsonld(self) -> int:
        return self._jsonld[1]


@dataclass
class SiteContext:
    """Everything a check may look at. Built once per run, then passed around."""

    domain: str
    base_url: str
    robots_txt: str | None
    robots_status: int | None
    # False when /robots.txt returned 200 with something that is not robots
    # syntax, which is the same as having no robots.txt at all.
    robots_is_real: bool
    agent_verdicts: list[AgentVerdict]
    # The sitemap that actually answered, or None. Kept apart from the one
    # robots.txt claims, because "no sitemap" and "declared but broken" are
    # different problems with different fixes.
    sitemap_url: str | None
    llms_txt: str | None
    pages: list[PageContext]
    # The body exactly as served, kept even when robots_is_real is False. A file
    # of nothing but comments carries no crawl rules and can still carry a
    # Content-Signal declaration, and that declaration is a fact about the file.
    robots_body: str | None = None
    sitemap_declared_url: str | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def readable_pages(self) -> list[PageContext]:
        """Only the pages that answered 200.

        A 404 in the sitemap is a real finding, and pages_reachable is the check
        that reports it. Charging the readability checks for the same page again
        would be counting one fault twice.
        """
        return [page for page in self.pages if page.status == 200]


class Check(Protocol):
    """The contract. One check per file under checks/."""

    check_id: str
    category: Category
    weight: int

    def __call__(self, site: SiteContext) -> CheckResult: ...


CheckFn = Callable[[SiteContext], CheckResult]


def check_meta(check_id: str, category: Category, weight: int):
    """Attach the contract to a check function. One line per check file."""

    def decorate(fn: CheckFn) -> CheckFn:
        fn.check_id = check_id  # type: ignore[attr-defined]
        fn.category = category  # type: ignore[attr-defined]
        fn.weight = weight  # type: ignore[attr-defined]
        return fn

    return decorate
