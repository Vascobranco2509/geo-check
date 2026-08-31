"""Read the `Content-Signal` directive some sites now put in robots.txt.

It is a declaration, not a rule: the site states what it is willing to have done
with its content by AI systems. Nothing here feeds a score, for the same reason
training posture does not. Saying what you allow is a business decision, and a
tool that deducts points for one of the answers is arguing rather than measuring.

The key set comes from measurement rather than from the draft specification. Of
the 906 sites in the corpus, 55 carry the directive, and what they actually send
is `search`, `ai-train`, `ai-input` and `use`. Two of the keys the draft
describes, `ai-personalization` and `ai-retrieval`, appear nowhere. Both sets are
accepted, because the draft is still moving and a site that follows it is not
making a mistake.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Observed in the wild, in descending order of how often they appear.
MEASURED_KEYS = {"search", "ai-train", "ai-input", "use"}
# Described by the draft but not yet seen in the corpus.
DRAFT_KEYS = {"ai-personalization", "ai-retrieval"}
KNOWN_KEYS = MEASURED_KEYS | DRAFT_KEYS

MEANING = {
    "search": "appearing in AI search results",
    "ai-train": "being used to train a model",
    "ai-input": "being quoted as input to an answer",
    "ai-personalization": "being used to personalise results",
    "ai-retrieval": "being retrieved to answer a question",
}

_LINE = re.compile(r"^\s*content-signal\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
# The explanatory block that ships with the directive, which some sites publish
# on its own. Its own wording says that without a signal nothing is granted or
# restricted, so the text alone declares nothing.
_BOILERPLATE = re.compile(r"content[ -]signals?\s*:", re.IGNORECASE)


@dataclass(frozen=True)
class ContentSignals:
    """What a site declared, and whether we understood all of it."""

    declared: dict[str, str]
    unknown_keys: list[str] = field(default_factory=list)
    raw: str = ""
    boilerplate_only: bool = False

    @property
    def present(self) -> bool:
        return bool(self.declared or self.unknown_keys)

    def summary(self) -> str:
        """One line a person can read, built only from keys we understand."""
        allows = [
            MEANING[k] for k, v in sorted(self.declared.items()) if k in MEANING and v == "yes"
        ]
        refuses = [
            MEANING[k] for k, v in sorted(self.declared.items()) if k in MEANING and v == "no"
        ]
        if self.boilerplate_only:
            return (
                "The site publishes the Content Signals terms and then declares no "
                "signal, which by those same terms grants and restricts nothing."
            )
        parts = []
        if allows:
            parts.append("allows " + _join(allows))
        if refuses:
            parts.append("refuses " + _join(refuses))
        if not parts:
            return "declares Content-Signal, but nothing we recognise"
        return "The site " + ", and ".join(parts) + "."


def _join(items: list[str]) -> str:
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


def parse(robots_txt: str | None) -> ContentSignals | None:
    """The declaration, or None when the site makes none.

    A site can repeat the directive. Later lines win on a repeated key, which is
    the same rule robots.txt uses for everything else.
    """
    if not robots_txt:
        return None
    matches = _LINE.findall(robots_txt)
    if not matches:
        # Eight sites in the corpus carry the terms and no directive. That is a
        # real state, not a miss, and it is worth telling the owner about.
        if _BOILERPLATE.search(robots_txt) and "content-signal" in robots_txt.lower():
            return ContentSignals(declared={}, raw="", boilerplate_only=True)
        return None

    declared: dict[str, str] = {}
    unknown: list[str] = []
    for value in matches:
        for pair in value.split(","):
            if "=" not in pair:
                continue
            key, _, val = pair.partition("=")
            key, val = key.strip().lower(), val.strip().lower()
            if not key:
                continue
            if key in KNOWN_KEYS:
                declared[key] = val
            elif key not in unknown:
                unknown.append(key)
    return ContentSignals(declared=declared, unknown_keys=unknown, raw="; ".join(matches))
