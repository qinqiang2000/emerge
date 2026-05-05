// Partial-feedback payload builder and types. Mirrors backend
// FeedbackIn / FeedbackCorrectionIn (backend/app/schemas/annotation.py)
// and the dotted/[n] path convention from
// backend/app/services/corrections.apply_feedback_corrections.
//
// Used by:
//   - API Console interactive test form (R8.6.b) — POSTs to
//     /extract/{api_code}/feedback with X-Api-Key.
//   - Studio Report-wrong dialog (R8.6.c) — renders the same JSON shape
//     read-only so users learn the public contract, but Lab posts a
//     regular Annotation rather than the public feedback endpoint.

export type FeedbackIssueType =
  | "wrong_value"
  | "missing_field"
  | "extra_field"
  | "wrong_entity_count"
  | "other";

export const FEEDBACK_ISSUE_TYPES: ReadonlyArray<FeedbackIssueType> = [
  "wrong_value",
  "missing_field",
  "extra_field",
  "wrong_entity_count",
  "other",
];

export interface FeedbackCorrection {
  entity_index: number;
  field_path: string;
  correct_value: unknown;
  comment?: string;
}

export interface PartialFeedbackPayload {
  request_id: number;
  corrections: FeedbackCorrection[];
  issue_type?: FeedbackIssueType;
  notes?: string;
}

export function fieldPathFor(
  _entityIndex: number,
  key: string,
  arrayIndex?: number,
): string {
  return arrayIndex === undefined ? key : `${key}[${arrayIndex}]`;
}

export function buildPartialFeedback(args: {
  predictionId: number;
  corrections: FeedbackCorrection[];
  issueType?: FeedbackIssueType;
  notes?: string;
}): PartialFeedbackPayload {
  const { predictionId, corrections, issueType, notes } = args;

  if (!Number.isInteger(predictionId)) {
    throw new Error("predictionId must be an integer");
  }
  if (predictionId <= 0) {
    throw new Error("predictionId must be positive");
  }
  if (corrections.length === 0) {
    throw new Error("at least one correction is required");
  }
  for (const c of corrections) {
    if (!Number.isInteger(c.entity_index) || c.entity_index < 0) {
      throw new Error("entity_index must be a non-negative integer");
    }
    if (typeof c.field_path !== "string" || c.field_path.length === 0) {
      throw new Error("field_path must be a non-empty string");
    }
  }
  if (issueType !== undefined && !FEEDBACK_ISSUE_TYPES.includes(issueType)) {
    throw new Error(`issue_type must be one of ${FEEDBACK_ISSUE_TYPES.join(", ")}`);
  }

  const payload: PartialFeedbackPayload = {
    request_id: predictionId,
    corrections,
  };
  if (issueType !== undefined) payload.issue_type = issueType;
  if (notes !== undefined) payload.notes = notes;
  return payload;
}
