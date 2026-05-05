import { describe, expect, it } from "vitest";

import {
  buildPartialFeedback,
  fieldPathFor,
  type FeedbackCorrection,
  type FeedbackIssueType,
  type PartialFeedbackPayload,
} from "@/lib/feedback";

describe("fieldPathFor — dotted/array path composition", () => {
  it("returns the bare key for a top-level field", () => {
    expect(fieldPathFor(0, "total")).toBe("total");
  });

  it("appends [n] when arrayIndex is supplied", () => {
    expect(fieldPathFor(0, "line_items", 2)).toBe("line_items[2]");
  });

  it("treats arrayIndex 0 as a real index, not a falsy skip", () => {
    expect(fieldPathFor(0, "line_items", 0)).toBe("line_items[0]");
  });

  it("composes into a child path when chained with a dot", () => {
    const leaf = fieldPathFor(0, "line_items", 2);
    expect(`${leaf}.price`).toBe("line_items[2].price");
  });

  it("entityIndex does not appear in the path string (entity_index is its own field)", () => {
    expect(fieldPathFor(7, "total")).toBe("total");
    expect(fieldPathFor(7, "line_items", 1)).toBe("line_items[1]");
  });
});

describe("buildPartialFeedback — payload shape", () => {
  const goodCorrection: FeedbackCorrection = {
    entity_index: 0,
    field_path: "total",
    correct_value: 1234,
  };

  it("emits the documented PartialFeedbackPayload shape", () => {
    const payload: PartialFeedbackPayload = buildPartialFeedback({
      predictionId: 42,
      corrections: [goodCorrection],
      issueType: "wrong_value",
      notes: "looked at receipt twice",
    });
    expect(payload).toEqual({
      request_id: 42,
      corrections: [goodCorrection],
      issue_type: "wrong_value",
      notes: "looked at receipt twice",
    });
  });

  it("omits issue_type and notes when not supplied", () => {
    const payload = buildPartialFeedback({
      predictionId: 42,
      corrections: [goodCorrection],
    });
    expect(payload).toEqual({ request_id: 42, corrections: [goodCorrection] });
    expect(payload).not.toHaveProperty("issue_type");
    expect(payload).not.toHaveProperty("notes");
  });

  it("rejects empty corrections list", () => {
    expect(() =>
      buildPartialFeedback({ predictionId: 42, corrections: [] }),
    ).toThrow(/at least one correction/i);
  });

  it("rejects non-positive request_id (mirrors backend prediction_id semantics)", () => {
    expect(() =>
      buildPartialFeedback({ predictionId: 0, corrections: [goodCorrection] }),
    ).toThrow(/positive/i);
    expect(() =>
      buildPartialFeedback({ predictionId: -1, corrections: [goodCorrection] }),
    ).toThrow(/positive/i);
  });

  it("rejects non-integer request_id", () => {
    expect(() =>
      buildPartialFeedback({
        predictionId: 1.5,
        corrections: [goodCorrection],
      }),
    ).toThrow(/integer/i);
  });

  it("accepts each of the five backend issue_type literals", () => {
    const literals: FeedbackIssueType[] = [
      "wrong_value",
      "missing_field",
      "extra_field",
      "wrong_entity_count",
      "other",
    ];
    for (const issueType of literals) {
      const payload = buildPartialFeedback({
        predictionId: 1,
        corrections: [goodCorrection],
        issueType,
      });
      expect(payload.issue_type).toBe(issueType);
    }
  });

  it("rejects an issue_type outside the five literals", () => {
    expect(() =>
      buildPartialFeedback({
        predictionId: 1,
        corrections: [goodCorrection],
        // @ts-expect-error — we are testing runtime rejection of bogus values
        issueType: "wrong_format",
      }),
    ).toThrow(/issue_type/i);
  });

  it("rejects a correction with empty field_path", () => {
    expect(() =>
      buildPartialFeedback({
        predictionId: 1,
        corrections: [{ entity_index: 0, field_path: "", correct_value: 1 }],
      }),
    ).toThrow(/field_path/i);
  });

  it("rejects a correction with negative entity_index", () => {
    expect(() =>
      buildPartialFeedback({
        predictionId: 1,
        corrections: [{ entity_index: -1, field_path: "total", correct_value: 1 }],
      }),
    ).toThrow(/entity_index/i);
  });

  it("preserves complex correct_value (objects, arrays, null)", () => {
    const corrections: FeedbackCorrection[] = [
      {
        entity_index: 0,
        field_path: "line_items[0]",
        correct_value: { price: 12, qty: 2 },
        comment: "missed the unit price",
      },
      {
        entity_index: 0,
        field_path: "discount",
        correct_value: null,
      },
    ];
    const payload = buildPartialFeedback({ predictionId: 9, corrections });
    expect(payload.corrections).toEqual(corrections);
  });
});
