// Mirror of backend/app/schemas/readiness.py — keep field names and types
// in sync. Status string unions match the discrete values produced by
// backend/app/services/readiness.py (build_readiness).

export type SchemaMaturityStatus =
  | "draft"
  | "stabilizing"
  | "lock_candidate"
  | "locked";

export type RegressionHealthStatus =
  | "no_production_feedback"
  | "passing"
  | "failing"
  | "unknown";

export type QualityEstimate = {
  score: number;
  judge_component: number;
  judge_precision: number;
  ci_low: number;
  ci_high: number;
  observation_count: number;
  vibe_check_size: number;
};

export type EvidenceCoverage = {
  reviewed_docs: number;
  reviewed_entities: number;
  reviewed_fields: number;
  field_evidence_fields: number;
  field_evidence_coverage_ratio: number;
};

export type SchemaMaturity = {
  status: SchemaMaturityStatus;
  reviewed_docs: number;
  reviewed_entities: number;
  recent_schema_breaking_changes: number;
  message: string;
};

export type RegressionHealth = {
  counterexamples_total: number;
  counterexample_component: number | null;
  status: RegressionHealthStatus;
};

export type RiskyField = {
  field_name: string;
  count: number;
};

export type APIReadinessOut = {
  quality_estimate: QualityEstimate;
  evidence_coverage: EvidenceCoverage;
  schema_maturity: SchemaMaturity;
  regression_health: RegressionHealth;
  risky_fields: RiskyField[];
  publish_blockers: string[];
  warnings: string[];
};
