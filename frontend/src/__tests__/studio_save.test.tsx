import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import { StudioPage } from "@/pages/Studio";
import { useStudio, type DocumentDetail } from "@/stores/studio";

const PREDICTION_ID = 9001;

const SEEDED_DOC: DocumentDetail = {
  id: 102,
  project_id: 7,
  filename: "receipt-001.pdf",
  mime_type: "application/pdf",
  page_count: 1,
  byte_size: 22222,
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

function renderStudio() {
  // Wrap with <ToastProvider> so the production-realistic save → toast
  // path is exercised end-to-end (dogfood follow-up #4).
  return render(
    <ToastProvider>
      <MemoryRouter initialEntries={["/projects/7/studio/102"]}>
        <Routes>
          <Route
            path="/projects/:id/studio/:did"
            element={<StudioPage />}
          />
        </Routes>
      </MemoryRouter>
    </ToastProvider>,
  );
}

async function settle() {
  await waitFor(() => {
    expect(useStudio.getState().loading).toBe(false);
    expect(useStudio.getState().saving).toBe(false);
  });
}

describe("StudioPage minimal correction save", () => {
  beforeEach(() => {
    useStudio.setState({
      doc: SEEDED_DOC,
      draft: SEEDED_DOC.latest_prediction!.output as Record<string, unknown>[],
      loading: false,
      saving: false,
      error: null,
    });
    vi.spyOn(api, "get").mockResolvedValue({ data: SEEDED_DOC });
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

  it("renders the predicted entity fields seeded from latest_prediction", async () => {
    renderStudio();
    await settle();
    expect(screen.getByDisplayValue("100")).toBeInTheDocument();
    expect(screen.getByDisplayValue("JPY")).toBeInTheDocument();
    expect(
      screen.getByText(/correct values here to mark this document reviewed/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/production api changes only when you activate a version/i),
    ).toBeInTheDocument();
  });

  it("seeds draft from latest_annotation when present (override)", async () => {
    const docWithAnnotation: DocumentDetail = {
      ...SEEDED_DOC,
      latest_annotation: {
        id: 5,
        output: [{ total: "999", currency: "JPY" }],
        role: "none",
        notes: null,
      },
    };
    vi.spyOn(api, "get").mockResolvedValue({ data: docWithAnnotation });
    useStudio.setState({
      doc: docWithAnnotation,
      draft: [{ total: "999", currency: "JPY" }],
      loading: false,
      saving: false,
      error: null,
    });
    renderStudio();
    await settle();
    expect(screen.getByDisplayValue("999")).toBeInTheDocument();
  });

  it("Save correction POSTs the patched output with parent_prediction_id", async () => {
    const post = vi
      .spyOn(api, "post")
      .mockResolvedValue({ data: { id: 123 } });

    renderStudio();
    await settle();

    fireEvent.change(screen.getByDisplayValue("100"), {
      target: { value: "200" },
    });

    fireEvent.click(screen.getByRole("button", { name: /save correction/i }));

    await waitFor(() => expect(post).toHaveBeenCalledTimes(1));
    expect(post).toHaveBeenCalledWith(
      "/api/v1/projects/7/documents/102/annotations",
      {
        output: [{ total: "200", currency: "JPY" }],
        parent_prediction_id: PREDICTION_ID,
      },
    );
    await settle();
  });

  it("Save success surfaces the 'Saved' toast pill (dogfood #4)", async () => {
    vi.spyOn(api, "post").mockResolvedValue({ data: { id: 123 } });
    renderStudio();
    await settle();

    fireEvent.change(screen.getByDisplayValue("100"), {
      target: { value: "200" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save correction/i }));
    await settle();

    // The Radix viewport is the well-known surface for any toast Root.
    const viewport = await screen.findByTestId("toast-viewport");
    expect(viewport.textContent ?? "").toMatch(/saved/i);
  });

  it("Save success after a prior failure still surfaces the toast", async () => {
    // Pre-seed a stale error to simulate a failed prior save still being
    // present in the store. handleSave must not gate the success toast on
    // "error stayed equal to its previous value" — `save` resets `error`
    // to null on entry, so a successful retry has error === null.
    useStudio.setState({ error: "errors.SOMETHING" });
    vi.spyOn(api, "post").mockResolvedValue({ data: { id: 123 } });

    renderStudio();
    await settle();

    fireEvent.change(screen.getByDisplayValue("100"), {
      target: { value: "200" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save correction/i }));
    await settle();

    const viewport = await screen.findByTestId("toast-viewport");
    expect(viewport.textContent ?? "").toMatch(/saved/i);
  });

  it("disables Save when draft equals seeded baseline", async () => {
    renderStudio();
    await settle();
    expect(
      screen.getByRole("button", { name: /save correction/i }),
    ).toBeDisabled();
  });

  it("save triggers readiness + review-queue refresh (auto-refresh wiring)", async () => {
    // R8.7 hygiene-tail: ReadinessPanel + ReviewInboxBanner used to show
    // stale state until the user reloaded the page after a correction.
    // The studio store now fires both stores' load() right after save.
    // Pin it: a successful save must hit both /readiness and
    // /review-queue at least once.
    vi.spyOn(api, "post").mockResolvedValue({ data: { id: 123 } });
    const get = vi.spyOn(api, "get").mockImplementation((url: string) => {
      if (url.endsWith("/readiness")) return Promise.resolve({ data: {} });
      if (url.endsWith("/review-queue"))
        return Promise.resolve({
          data: { required_review: [], spot_check: [], all: [], schema_locked: true },
        });
      return Promise.resolve({ data: SEEDED_DOC });
    });

    renderStudio();
    await settle();
    fireEvent.change(screen.getByDisplayValue("100"), {
      target: { value: "200" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save correction/i }));
    await settle();

    const urls = get.mock.calls.map((c) => c[0] as string);
    expect(urls).toContain("/api/v1/projects/7/readiness");
    expect(urls).toContain("/api/v1/projects/7/review-queue");
  });
});
