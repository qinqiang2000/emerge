from pydantic import BaseModel


class QualityEstimateOut(BaseModel):
    score: float
    judge_component: float
    judge_precision: float
    ci_low: float
    ci_high: float
    observation_count: int
    vibe_check_size: int


class EvidenceCoverageOut(BaseModel):
    reviewed_docs: int
    reviewed_entities: int
    reviewed_fields: int
    field_evidence_fields: int
    field_evidence_coverage_ratio: float


class SchemaMaturityOut(BaseModel):
    # draft | stabilizing | lock_candidate | locked
    status: str
    reviewed_docs: int
    reviewed_entities: int
    recent_schema_breaking_changes: int
    message: str


class RegressionHealthOut(BaseModel):
    counterexamples_total: int
    counterexample_component: float | None
    # no_production_feedback | passing | failing | unknown
    status: str


class RiskyFieldOut(BaseModel):
    field_name: str
    count: int


class APIReadinessOut(BaseModel):
    quality_estimate: QualityEstimateOut
    evidence_coverage: EvidenceCoverageOut
    schema_maturity: SchemaMaturityOut
    regression_health: RegressionHealthOut
    risky_fields: list[RiskyFieldOut]
    publish_blockers: list[str]
    warnings: list[str]
