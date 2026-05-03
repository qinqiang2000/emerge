import pytest

from app.engine.regression import (
    counterexample_regression_score,
    structurally_matches,
)


def test_match_identical_arrays():
    assert structurally_matches([{"a": 1}], [{"a": 1}]) is True


def test_mismatch_array_length():
    assert structurally_matches([{"a": 1}], [{"a": 1}, {"a": 2}]) is False


def test_match_with_number_tolerance():
    assert structurally_matches([{"x": 1.001}], [{"x": 1.0}]) is True
    assert structurally_matches([{"x": 1.5}], [{"x": 1.0}]) is False


def test_string_normalization():
    assert structurally_matches([{"s": "  Hello "}], [{"s": "hello"}]) is True


def test_field_set_difference():
    assert structurally_matches([{"a": 1}], [{"a": 1, "b": 2}]) is False


def test_nested_array_recursion():
    a = [{"items": [{"qty": 2}, {"qty": 3}]}]
    b = [{"items": [{"qty": 2.0}, {"qty": 3.0}]}]
    assert structurally_matches(a, b) is True


@pytest.mark.asyncio
async def test_regression_score_empty_pool_is_one():
    score = await counterexample_regression_score(counterexamples=[], rerun=lambda doc_id: [])
    assert score == 1.0


@pytest.mark.asyncio
async def test_regression_score_partial_hit():
    examples = [
        {"document_id": 1, "expected": [{"a": 1}]},
        {"document_id": 2, "expected": [{"a": 2}]},
        {"document_id": 3, "expected": [{"a": 3}]},
    ]
    scoring = {1: [{"a": 1}], 2: [{"a": 99}], 3: [{"a": 3}]}

    async def rerun(doc_id):
        return scoring[doc_id]

    score = await counterexample_regression_score(
        counterexamples=examples, rerun=rerun
    )
    assert score == pytest.approx(2 / 3)
