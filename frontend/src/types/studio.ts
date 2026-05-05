// Mirror of backend Prediction.per_field_evidence / per_field_confidence
// surfaced under DocumentDetailOut.latest_prediction. Spec §3.2 / §8.2:
// evidence shape is page / quote / rationale / source_text_hash only.
// NEVER add bbox, coordinates, polygon, region, or span here.

export type ConfidenceVerdict = "up" | "down" | "uncertain";

export type FieldEvidence = {
  page?: number;
  quote?: string;
  rationale?: string;
  source_text_hash?: string;
};

// Outer key is entity index (string-coerced JSON map key); inner key is
// field name. Both maps are nullable on the wire to match the backend
// model: per_field_confidence defaults to {}, per_field_evidence is
// nullable.
export type PerFieldEvidence = Record<string, Record<string, FieldEvidence>>;
export type PerFieldConfidence = Record<
  string,
  Record<string, ConfidenceVerdict>
>;

export const EVIDENCE_ALLOWED_KEYS: ReadonlyArray<keyof FieldEvidence> = [
  "page",
  "quote",
  "rationale",
  "source_text_hash",
];
