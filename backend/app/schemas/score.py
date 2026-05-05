from pydantic import BaseModel


class ProjectScoreOut(BaseModel):
    score: float
    judge_component: float
    ce_component: float
    observation_count: int
    vibe_check_size: int


class CalibrationOut(BaseModel):
    tp: int
    fp: int
    fn: int
    tn: int
    point_estimate: float
    ci_low: float
    ci_high: float
    observation_count: int


class ReviewItemOut(BaseModel):
    id: int
    filename: str
    flagged_fields: list[str]


class ReviewQueueOut(BaseModel):
    required_review: list[ReviewItemOut]
    spot_check: list[ReviewItemOut]
    all: list[ReviewItemOut]
    schema_locked: bool  # True iff active version is locked (spec §4.1).
    # Frontend renders a "Schema is in Draft — corrected docs stay here so
    # you can revisit" callout when False, so the user understands why a
    # doc they just corrected hasn't disappeared.


class JudgeRunOut(BaseModel):
    judged_predictions: list[int]
    failed_predictions: list[int]
