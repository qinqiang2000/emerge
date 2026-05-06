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
  it("opens as Report issue and explains the action does not correct or train", () => {
    render(
      <FlagFieldMenu projectId={9} entityIndex={0} fieldName="total" />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: /report issue for total/i }),
    );
    expect(
      screen.getByRole("heading", { name: /report issue/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/does not change this value/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/does not count toward schema lock/i),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText(/issue type/i),
    ).toBeInTheDocument();
  });

  it("does NOT offer 'wrong_value' (textbox edit is the value-correction path)", () => {
    // dogfood follow-up #3 explicitly: editing the textbox is the only
    // value-correction path. Surfacing wrong_value in the flag-without-
    // correcting menu re-creates the dual-affordance the dogfood walk
    // complained about — pin the absence so a later "complete the enum"
    // refactor can't slip it back in.
    render(
      <FlagFieldMenu projectId={9} entityIndex={0} fieldName="total" />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: /report issue for total/i }),
    );
    const select = screen.getByLabelText(/issue type/i) as HTMLSelectElement;
    const optionValues = Array.from(select.options).map((o) => o.value);
    expect(optionValues).not.toContain("wrong_value");
    // The default must be a non-value-fix kind so a user who clicks
    // through without changing the dropdown can't accidentally re-create
    // the dual path.
    expect(select.value).toBe("missing_field");
  });

  it("flag-without-correcting POSTs an Annotation with unchanged output and notes-encoded issue_type", async () => {
    const post = vi.spyOn(api, "post").mockResolvedValue({ data: {} });
    vi.spyOn(api, "get").mockResolvedValue({ data: DOC });

    render(
      <FlagFieldMenu projectId={9} entityIndex={0} fieldName="total" />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: /report issue for total/i }),
    );
    fireEvent.change(screen.getByLabelText(/issue type/i), {
      target: { value: "missing_field" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^report issue$/i }));

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
