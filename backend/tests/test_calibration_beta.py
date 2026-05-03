import pytest

from app.engine.score import (
    PRIOR_ALPHA,
    PRIOR_BETA,
    beta_posterior,
    precision_ci_95,
    precision_point_estimate,
)


def test_default_prior_is_8_2():
    assert (PRIOR_ALPHA, PRIOR_BETA) == (8, 2)


def test_posterior_uses_only_tp_fp():
    a, b = beta_posterior(tp=5, fp=3)
    assert a == 8 + 5
    assert b == 2 + 3


def test_point_estimate_at_prior_is_eighty_percent():
    a, b = beta_posterior(tp=0, fp=0)
    assert precision_point_estimate(a, b) == pytest.approx(0.80, abs=1e-6)


def test_ci_collapses_with_data():
    wide_lo, wide_hi = precision_ci_95(*beta_posterior(tp=0, fp=0))
    narrow_lo, narrow_hi = precision_ci_95(*beta_posterior(tp=50, fp=5))
    assert (wide_hi - wide_lo) > (narrow_hi - narrow_lo)


def test_ci_inside_zero_one():
    lo, hi = precision_ci_95(*beta_posterior(tp=10, fp=5))
    assert 0 <= lo <= hi <= 1
