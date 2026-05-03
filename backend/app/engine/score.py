from enum import Enum

from scipy import stats

PRIOR_ALPHA = 8
PRIOR_BETA = 2

DEFAULT_JUDGE_WEIGHT = 0.7
DEFAULT_CE_WEIGHT = 0.3


class JudgeVerdict(str, Enum):
    UP = "up"
    DOWN = "down"
    UNCERTAIN = "uncertain"


class HumanVerdict(str, Enum):
    UP = "up"
    DOWN = "down"
    FIXED = "fixed"      # human corrected the value
    SKIPPED = "skipped"  # human shown but did nothing
    NOT_SEEN = "not_seen"  # human has not been shown this field


def verdict_pair_weight(
    judge: JudgeVerdict, human: HumanVerdict, *, calibrated: float = 0.8
) -> float:
    """Spec §4.1 verdict pair → weight table."""
    if judge is JudgeVerdict.UP and human is HumanVerdict.UP:
        return 1.0
    if judge is JudgeVerdict.UP and human is HumanVerdict.DOWN:
        return 0.0
    if judge is JudgeVerdict.UP and human is HumanVerdict.NOT_SEEN:
        return calibrated
    if judge in (JudgeVerdict.DOWN, JudgeVerdict.UNCERTAIN) and human is HumanVerdict.FIXED:
        return 1.0
    if judge in (JudgeVerdict.DOWN, JudgeVerdict.UNCERTAIN) and human is HumanVerdict.SKIPPED:
        return 0.0
    if judge in (JudgeVerdict.DOWN, JudgeVerdict.UNCERTAIN) and human is HumanVerdict.DOWN:
        return 0.0
    if judge is JudgeVerdict.UP and human is HumanVerdict.FIXED:
        return 1.0  # judge said up, human still fixed → benefit of the doubt: weight 1
    return 0.0  # any other combination is treated as 0


def compute_judge_component(
    pairs: list[tuple[JudgeVerdict, HumanVerdict]],
    *,
    judge_precision_calibrated: float,
) -> float:
    if not pairs:
        return 1.0  # no fields → trivially perfect
    total = 0.0
    for j, h in pairs:
        total += verdict_pair_weight(j, h, calibrated=judge_precision_calibrated)
    return total / len(pairs)


def compute_score(
    *,
    judge_component: float,
    ce_score: float | None,
    judge_weight: float = DEFAULT_JUDGE_WEIGHT,
    ce_weight: float = DEFAULT_CE_WEIGHT,
) -> float:
    """`ce_score=None` denotes empty counterexample pool → treated as 1.0 per spec."""
    ce = 1.0 if ce_score is None else ce_score
    return judge_weight * judge_component + ce_weight * ce


def beta_posterior(*, tp: int, fp: int) -> tuple[float, float]:
    return PRIOR_ALPHA + tp, PRIOR_BETA + fp


def precision_point_estimate(alpha: float, beta: float) -> float:
    return alpha / (alpha + beta)


def precision_ci_95(alpha: float, beta: float) -> tuple[float, float]:
    lo = stats.beta.ppf(0.025, alpha, beta)
    hi = stats.beta.ppf(0.975, alpha, beta)
    return float(lo), float(hi)
