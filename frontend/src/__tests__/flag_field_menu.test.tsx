import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FlagFieldMenu } from "@/components/FlagFieldMenu";
import { api } from "@/lib/api";
import { useStudio, type DocumentDetail } from "@/stores/studio";

const PRED_ID = 7777;

const DOC: DocumentDetail = {
  id: 42,
  project_id: 9,
  filename: "r.pdf",
  mime_type: "application/pdf",
  page_count: 1,
  byte_size: 100,
  status: "extracted",
  created_at: "2026-05-06T00:00:00Z",
  latest_prediction: {
    id: PRED_ID,
    output: [{ total: "100", currency: "JPY" }],
    status: "ok",
    model_id: "m",
    tokens_used: 1,
    error_message: null,
  },
  latest_annotation: null,
};

beforeEach(() => {
  useStudio.setState({
    doc: DOC,
    draft: DOC.latest_prediction!.output as Record<string, unknown>[],
    loading: false,
    saving: false,
    error: null,
  });
});
afterEach(() => {
  vi.restoreAllMocks();
  useStudio.setState({
    doc: null,
    draft: [],
    loading: false,
    saving: false,
    error: null,
  });
});

describe("FlagFieldMenu (dogfood follow-up #3)", () => {
  it("opens via the ⋮ trigger and shows the issue_type select", () => {
    render(
      <FlagFieldMenu projectId={9} entityIndex={0} fieldName="total" />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: /more actions for total/i }),
    );
    expect(
      screen.getByLabelText(/issue type/i),
    ).toBeInTheDocument();
  });

  it("flag-without-correcting POSTs an Annotation with unchanged output and notes-encoded issue_type", async () => {
    const post = vi.spyOn(api, "post").mockResolvedValue({ data: {} });
    vi.spyOn(api, "get").mockResolvedValue({ data: DOC });

    render(
      <FlagFieldMenu projectId={9} entityIndex={0} fieldName="total" />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: /more actions for total/i }),
    );
    fireEvent.change(screen.getByLabelText(/issue type/i), {
      target: { value: "missing_field" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^flag$/i }));

    await waitFor(() => expect(post).toHaveBeenCalled());
    const [url, body] = post.mock.calls[0]!;
    expect(url).toBe("/api/v1/projects/9/documents/42/annotations");
    // Output must be unchanged — the menu is for flag-without-correcting.
    expect(body).toMatchObject({
      output: [{ total: "100", currency: "JPY" }],
      parent_prediction_id: PRED_ID,
    });
    const notes = String((body as Record<string, unknown>).notes ?? "");
    expect(notes).toContain("[lab_flag]");
    expect(notes).toContain("missing_field");
    // CRITICAL: must never call the public feedback endpoint from Lab.
    for (const call of post.mock.calls) {
      expect(String(call[0])).not.toContain("/feedback");
    }
  });
});
