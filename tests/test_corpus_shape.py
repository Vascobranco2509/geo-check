"""The corpus file must not regain a shape that states how the corpus divides.

How the corpus divides is the maintainer's article and is deliberately absent from
this repository. Three separate attempts to remove it left it in: the first
removed the sentence and kept the counts, the second removed the counts and kept
the sections whose sizes were the counts, and later prose reintroduced a figure
while describing the removal.

A habit that has failed that often is not a habit, it is a test.
"""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "data" / "corpus.txt"
CATEGORIES = ROOT / "data" / "corpus_categories.csv"

# The vocabulary CONTRIBUTING.md documents. Kept here rather than derived from
# the file, because a set read out of the data agrees with the data by
# construction and would catch nothing.
KNOWN_TYPES = {
    "b2b",
    "blog",
    "ecommerce",
    "education",
    "government",
    "news",
    "parked",
    "platform",
    "reference",
    "saas",
    "storefront",
}


def read_lines() -> list[str]:
    return CORPUS.read_text(encoding="utf-8").splitlines()


def domains() -> list[str]:
    return [
        line.strip() for line in read_lines() if line.strip() and not line.strip().startswith("#")
    ]


def test_the_corpus_is_one_flat_block_with_no_sections():
    """A section boundary is a count, whether or not anybody prints the count."""
    lines = read_lines()
    first = next(i for i, line in enumerate(lines) if line.strip() and not line.startswith("#"))
    last = max(i for i, line in enumerate(lines) if line.strip() and not line.startswith("#"))
    interruptions = [
        (i + 1, lines[i])
        for i in range(first, last)
        if lines[i].startswith("#") and lines[i].strip() != "#"
    ]
    assert not interruptions, f"comment lines inside the domain block: {interruptions}"


def test_the_corpus_is_ordered_by_hash_so_the_order_carries_nothing():
    entries = domains()
    assert entries == sorted(entries, key=lambda d: hashlib.sha256(d.encode()).hexdigest())


def test_the_site_type_vocabulary_is_closed():
    """A type has to be decided on, not arrive.

    `b2b` and `parked` were in the data while CONTRIBUTING.md named nine types
    and claimed ten. Nothing was checking, so a category could appear without
    anybody choosing it, and a documented vocabulary that disagrees with the
    file it documents is worse than no vocabulary at all.
    """
    with CATEGORIES.open(encoding="utf-8", newline="") as handle:
        found = {row["category"] for row in csv.DictReader(handle)}

    assert found == KNOWN_TYPES, f"undocumented site type: {sorted(found - KNOWN_TYPES)}"


def test_every_domain_has_a_site_type_and_no_type_is_half_the_corpus():
    entries = domains()
    with CATEGORIES.open(encoding="utf-8", newline="") as handle:
        types = {row["domain"]: row["category"] for row in csv.DictReader(handle)}

    missing = [d for d in entries if d not in types]
    assert not missing, f"no site type for {missing}"
    extra = sorted(set(types) - set(entries))
    assert not extra, f"site type for domains not in the corpus: {extra}"

    counts: dict[str, int] = {}
    for domain in entries:
        counts[types[domain]] = counts.get(types[domain], 0) + 1
    half = len(entries) // 2
    oversized = {name: n for name, n in counts.items() if n >= half}
    assert not oversized, f"a type large enough to partition the corpus: {oversized}"
