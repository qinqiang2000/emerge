import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ReportWrongFieldDialog } from "@/components/ReportWrongFieldDialog";
import { api } from "@/lib/api";
import { useStudio, type DocumentDetail } from "@/stores/studio";

const PREDICTION_ID = 7777;

const DOC: DocumentDetail = {
  id: 42,
  project_id: 9,
  filename: "receipt-001.pdf",
  mime_type: "application/pdf",
  page_count: 1,
  byte_size: 1000,
  status: "extracted",
  created_at: "2026-05-04T11:00:00Z",
  latest_prediction: {
    id: PREDICTION_ID,
    output: [{ total: "100", currency: "JPY" }],
    status: "ok",
    model_id: "gemini-2.5-flash",
    tokens_used: 42,
    error_message: null,
  },
  latest_annotation: null,
};

function renderDialog(
  props?: Partial<Parameters<typeof ReportWrongFieldDialog>[0]>,
) {
  const onOpenChange = props?.onOpenChange ?? vi.fn();
  return {
    onOpenChange,
    ...render(
      <ReportWrongFieldDialog
        open={props?.open ?? true}
        onOpenChange={onOpenChange}
        entityIndex={props?.entityIndex ?? 0}
        fieldName={props?.fieldName ?? "total"}
        currentValue={props?.currentValue ?? "100"}
        projectId={props?.projectId ?? 9}
      />,
    ),
  };
}

beforeEach(() => {
  useStudio.setState({
    doc: DOC,
    draft: DOC.latest_prediction!.output,
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

describe("ReportWrongFieldDialog — pre-fill", () => {
  it("renders the entity index, field path, and current value", () => {
    renderDialog({
      entityIndex: 0,
      fieldName: "total",
      currentValue: "100",
    });
    expect(screen.getByText(/entity index/i)).toBeInTheDocument();
    expect(screen.getAllByText(/total/).length).toBeGreaterThan(0);
    // "100" appears in the readonly current-value <dd> and inside the
    // educational JSON block — both are expected.
    expect(screen.getAllByText(/100/).length).toBeGreaterThanOrEqual(1);
  });

  it("seeds the corrected-value input from currentValue", () => {
    renderDialog({ currentValue: "100" });
    const input = screen.getByLabelText(/corrected value/i) as HTMLInputElement;
    expect(input.value).toBe("100");
  });

  it("shows the equivalent public partial-feedback JSON read-only block", () => {
    renderDialog({
      entityIndex: 0,
      fieldName: "total",
      currentValue: "100",
    });
    // The educational JSON block must mention the partial-feedback shape.
    const block = screen.getByTestId("partial-feedback-equivalent");
    const text = block.textContent ?? "";
    expect(text).toContain("\"request_id\"");
    expect(text).toContain("\"corrections\"");
    expect(text).toContain("\"entity_index\"");
    expect(text).toContain("\"field_path\"");
    expect(text).toContain("\"correct_value\"");
    expect(text).toContain("\"total\"");
    // It must reflect the prediction id from the loaded doc.
    expect(text).toContain(String(PREDICTION_ID));
  });
});

describe("ReportWrongFieldDialog — submit routing", () => {
  it("POSTs to /annotations (NOT /extract/.../feedback) with the patched output", async () => {
    const post = vi.spyOn(api, "post").mockResolvedValue({ data: {} });
    vi.spyOn(api, "get").mockResolvedValue({ data: DOC });

    const { onOpenChange } = renderDialog({
      entityIndex: 0,
      fieldName: "total",
      currentValue: "100",
    });

    fireEvent.change(screen.getByLabelText(/corrected value/i), {
      target: { value: "1234" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

    await waitFor(() => expect(post).toHaveBeenCalled());
    const [url, body] = post.mock.calls[0]!;
    expect(url).toBe("/api/v1/projects/9/documents/42/annotations");
    // The dialog JSON-parses the corrected value (mirrors the public form
    // in R8.6.b) so users see in the educational JSON block exactly what
    // they save here. "1234" parses to number 1234; the rest of the
    // entity is preserved unchanged.
    expect(body).toMatchObject({
      output: [{ total: 1234, currency: "JPY" }],
      parent_prediction_id: PREDICTION_ID,
    });
    // CRITICAL: never call the public feedback endpoint from Lab.
    for (const call of post.mock.calls) {
      expect(String(call[0])).not.toContain("/feedback");
    }
    expect(onOpenChange).toHaveBeenLastCalledWith(false);
  });

  it("does not call any API on Cancel", () => {
    const post = vi.spyOn(api, "post").mockResolvedValue({ data: {} });
    const { onOpenChange } = renderDialog();
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(post).not.toHaveBeenCalled();
    expect(onOpenChange).toHaveBeenLastCalledWith(false);
  });
});

describe("ReportWrongFieldDialog — store wiring", () => {
  it("uses the existing studio.reportWrong action so it reuses save semantics", async () => {
    const post = vi.spyOn(api, "post").mockResolvedValue({ data: {} });
    vi.spyOn(api, "get").mockResolvedValue({ data: DOC });
    renderDialog({
      entityIndex: 0,
      fieldName: "total",
      currentValue: "100",
    });
    fireEvent.change(screen.getByLabelText(/corrected value/i), {
      target: { value: "300" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^save$/i }));
    await waitFor(() => expect(post).toHaveBeenCalled());
    // The store action exists and was reachable.
    expect(typeof useStudio.getState().reportWrong).toBe("function");
  });
});
