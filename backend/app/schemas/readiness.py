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
    # `annotated_*` (saved Annotations on Lab docs) and
    # `field_evidence_*` (per-field quote evidence) intentionally collide on
    # the same surface, so naming them by what they actually count avoids
    # the dogfood-#7 confusion of "72 fields reviewed" vs "0% with field
    # evidence".
    annotated_docs: int
    annotated_entities: int
    annotated_fields: int
    field_evidence_fields: int
    field_evidence_coverage_ratio: float


class SchemaMaturityOut(BaseModel):
    # draft | stabilizing | lock_candidate | locked
    status: str
    annotated_docs: int
    annotated_entities: int
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
