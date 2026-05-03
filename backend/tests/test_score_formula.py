import pytest

from app.engine.score import (
    HumanVerdict,
    JudgeVerdict,
    compute_judge_component,
    compute_score,
    verdict_pair_weight,
)


def test_pair_weights_match_spec():
    # spec §4.1 table
    assert verdict_pair_weight(JudgeVerdict.UP, HumanVerdict.UP) == 1.0
    assert verdict_pair_weight(JudgeVerdict.UP, HumanVerdict.DOWN) == 0.0
    assert verdict_pair_weight(JudgeVerdict.UP, HumanVerdict.NOT_SEEN, calibrated=0.82) == 0.82
    assert verdict_pair_weight(JudgeVerdict.DOWN, HumanVerdict.FIXED) == 1.0
    assert verdict_pair_weight(JudgeVerdict.DOWN, HumanVerdict.SKIPPED) == 0.0
    assert verdict_pair_weight(JudgeVerdict.DOWN, HumanVerdict.DOWN) == 0.0
    assert verdict_pair_weight(JudgeVerdict.UNCERTAIN, HumanVerdict.FIXED) == 1.0


def test_judge_component_average():
    pairs = [
        (JudgeVerdict.UP, HumanVerdict.UP),
        (JudgeVerdict.UP, HumanVerdict.UP),
        (JudgeVerdict.DOWN, HumanVerdict.SKIPPED),
        (JudgeVerdict.DOWN, HumanVerdict.FIXED),
    ]
    out = compute_judge_component(pairs, judge_precision_calibrated=0.8)
    assert out == (1.0 + 1.0 + 0.0 + 1.0) / 4


def test_judge_component_uses_calibrated_when_human_unseen():
    pairs = [(JudgeVerdict.UP, HumanVerdict.NOT_SEEN)]
    assert compute_judge_component(pairs, judge_precision_calibrated=0.7) == 0.7


def test_compute_score_default_weights():
    assert compute_score(judge_component=1.0, ce_score=1.0) == 1.0
    assert compute_score(judge_component=0.5, ce_score=0.5) == 0.5
    assert compute_score(judge_component=0.8, ce_score=0.4) == pytest.approx(0.7 * 0.8 + 0.3 * 0.4)


def test_compute_score_returns_one_when_ce_pool_empty_marker():
    """When ce_score is exactly None it means pool is empty → use 1.0 (spec §4.1)."""
    assert compute_score(judge_component=0.6, ce_score=None) == pytest.approx(0.7 * 0.6 + 0.3 * 1.0)


def test_compute_score_custom_weights():
    assert compute_score(
        judge_component=1.0, ce_score=0.0, judge_weight=0.5, ce_weight=0.5
    ) == 0.5
