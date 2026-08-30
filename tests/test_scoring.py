"""Tests for the rubric. These run offline and must stay fast."""

from geo_check.models import Category, CheckResult, Severity
from geo_check.scoring import (
    ACCESS_WEIGHTS,
    CAP_ALL_CITATION_BLOCKED,
    CAP_BLANKET_DISALLOW,
    READABILITY_WEIGHTS,
    grade,
    score_category,
    training_posture,
)


def _result(check_id: str, ratio: float, category: Category) -> CheckResult:
    return CheckResult(
        check_id=check_id,
        category=category,
        ratio=ratio,
        severity=Severity.OK,
        title=check_id,
        evidence="test",
    )


def test_rubrics_sum_to_one_hundred():
    assert sum(ACCESS_WEIGHTS.values()) == 100
    assert sum(READABILITY_WEIGHTS.values()) == 100


def test_grade_boundaries():
    assert grade(100) == "A"
    assert grade(90) == "A"
    assert grade(89.9) == "B"
    assert grade(75) == "B"
    assert grade(60) == "C"
    assert grade(40) == "D"
    assert grade(39.9) == "F"


def test_perfect_access_run():
    results = [_result(cid, 1.0, Category.ACCESS) for cid in ACCESS_WEIGHTS]
    breakdown = score_category(results, Category.ACCESS)
    assert breakdown.final_score == 100
    assert breakdown.letter == "A"
    assert breakdown.cap_applied is None


def test_missing_check_counts_as_zero():
    results = [_result(cid, 1.0, Category.ACCESS) for cid in ACCESS_WEIGHTS]
    results = [r for r in results if r.check_id != "no_noindex"]
    breakdown = score_category(results, Category.ACCESS)
    assert breakdown.final_score == 95


def test_blanket_disallow_cap_beats_citation_cap():
    results = [_result(cid, 1.0, Category.ACCESS) for cid in ACCESS_WEIGHTS]
    caps = [
        (CAP_ALL_CITATION_BLOCKED, "all citation crawlers blocked"),
        (CAP_BLANKET_DISALLOW, "blanket disallow"),
    ]
    breakdown = score_category(results, Category.ACCESS, caps=caps)
    assert breakdown.final_score == CAP_BLANKET_DISALLOW
    assert breakdown.cap_applied == "blanket disallow"


def test_cap_does_not_raise_a_low_score():
    results = [_result(cid, 0.0, Category.ACCESS) for cid in ACCESS_WEIGHTS]
    caps = [(CAP_ALL_CITATION_BLOCKED, "all citation crawlers blocked")]
    breakdown = score_category(results, Category.ACCESS, caps=caps)
    assert breakdown.final_score == 0


def test_training_posture():
    assert training_posture(5, 5) == "open"
    assert training_posture(0, 5) == "closed"
    assert training_posture(2, 5) == "partial"
    assert training_posture(0, 0) == "unknown"
