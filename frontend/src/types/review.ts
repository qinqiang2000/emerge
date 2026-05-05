// Mirror of backend/app/schemas/score.py — ReviewQueueOut + ReviewItemOut.
// `flagged_fields` is already capped at 3 by the backend; keep that contract.

export type ReviewItemOut = {
  id: number;
  filename: string;
  flagged_fields: string[];
};

export type ReviewQueueOut = {
  required_review: ReviewItemOut[];
  spot_check: ReviewItemOut[];
  all: ReviewItemOut[];
  schema_locked: boolean;
};
