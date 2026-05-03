import unicodedata
from collections.abc import Awaitable, Callable
from typing import Any

_NUMERIC_TOL = 1e-2


def _norm_string(s: str) -> str:
    return unicodedata.normalize("NFC", s).strip().lower()


def _values_equivalent(a: Any, b: Any) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) <= _NUMERIC_TOL
    if isinstance(a, str) and isinstance(b, str):
        return _norm_string(a) == _norm_string(b)
    if isinstance(a, list) and isinstance(b, list):
        return structurally_matches(a, b) if all(isinstance(x, dict) for x in a + b) else _list_eq(a, b)
    if isinstance(a, dict) and isinstance(b, dict):
        return _dict_eq(a, b)
    return a == b


def _list_eq(a: list, b: list) -> bool:
    if len(a) != len(b):
        return False
    return all(_values_equivalent(x, y) for x, y in zip(a, b))


def _dict_eq(a: dict, b: dict) -> bool:
    if set(a.keys()) != set(b.keys()):
        return False
    return all(_values_equivalent(a[k], b[k]) for k in a)


def structurally_matches(pred: list[dict], expected: list[dict]) -> bool:
    if len(pred) != len(expected):
        return False
    return all(_dict_eq(p, e) for p, e in zip(pred, expected))


async def counterexample_regression_score(
    *,
    counterexamples: list[dict],
    rerun: Callable[[int], Awaitable[list[dict]]],
) -> float:
    """`counterexamples` items: {document_id, expected: list[dict]}.
    `rerun(doc_id)` is awaitable returning the re-predicted output to compare against.
    """
    if not counterexamples:
        return 1.0
    hits = 0
    for ce in counterexamples:
        actual = await rerun(ce["document_id"])
        if structurally_matches(actual, ce["expected"]):
            hits += 1
    return hits / len(counterexamples)
