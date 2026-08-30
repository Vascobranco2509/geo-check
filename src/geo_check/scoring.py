"""The rubric. These numbers are a closed decision, see CLAUDE.md.

Two scores, never averaged. Training crawlers are worth zero points on purpose:
blocking model training is a legitimate business choice, not a mistake, and a
tool that punishes it is lying to the person reading the report.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import Category, CheckResult, Severity

ACCESS_WEIGHTS: dict[str, int] = {
    "citation_crawlers_allowed": 50,
    "user_fetch_crawlers_allowed": 20,
    "pages_reachable": 15,
    "sitemap_available": 10,
    "no_noindex": 5,
}

READABILITY_WEIGHTS: dict[str, int] = {
    "raw_html_content": 30,
    "jsonld_valid": 20,
    "heading_structure": 15,
    "title_and_description": 10,
    "author_and_dates": 10,
    "canonical": 5,
    "llms_txt": 5,
    "answer_shaped_content": 5,
}

# Critical failures cap the Access score regardless of everything else. A pretty
# average hiding a total block would be a lie.
CAP_ALL_CITATION_BLOCKED = 20
CAP_BLANKET_DISALLOW = 10

GRADE_THRESHOLDS: list[tuple[int, str]] = [
    (90, "A"),
    (75, "B"),
    (60, "C"),
    (40, "D"),
    (0, "F"),
]


def grade(score: float) -> str:
    for threshold, letter in GRADE_THRESHOLDS:
        if score >= threshold:
            return letter
    return "F"


@dataclass
class ScoreBreakdown:
    category: Category
    raw_score: float
    final_score: float
    letter: str
    cap_applied: str | None = None
    lines: list[dict] = field(default_factory=list)


def _weights_for(category: Category) -> dict[str, int]:
    return ACCESS_WEIGHTS if category is Category.ACCESS else READABILITY_WEIGHTS


def score_category(
    results: list[CheckResult],
    category: Category,
    caps: list[tuple[int, str]] | None = None,
) -> ScoreBreakdown:
    """Sum weighted results, then apply the lowest cap that fired.

    A missing check counts as zero rather than shrinking the denominator. A run
    that failed to collect evidence should not be rewarded for it.
    """
    weights = _weights_for(category)
    relevant = [r for r in results if r.category is category]
    by_id = {r.check_id: r for r in relevant}

    total = 0.0
    lines: list[dict] = []
    for check_id, weight in weights.items():
        result = by_id.get(check_id)
        earned = weight * result.ratio if result else 0.0
        total += earned
        lines.append(
            {
                "check_id": check_id,
                "weight": weight,
                "earned": round(earned, 2),
                "severity": result.severity.value if result else Severity.WARNING.value,
                "evidence": result.evidence if result else "check did not run",
            }
        )

    raw = round(total, 2)
    final = raw
    cap_reason: str | None = None
    for cap_value, reason in sorted(caps or [], key=lambda c: c[0]):
        if final > cap_value:
            final = float(cap_value)
            cap_reason = reason
            break

    return ScoreBreakdown(
        category=category,
        raw_score=raw,
        final_score=final,
        letter=grade(final),
        cap_applied=cap_reason,
        lines=lines,
    )


def training_posture(allowed: int, total: int) -> str:
    """Informational only. Never feeds a score."""
    if total == 0:
        return "unknown"
    if allowed == total:
        return "open"
    if allowed == 0:
        return "closed"
    return "partial"
