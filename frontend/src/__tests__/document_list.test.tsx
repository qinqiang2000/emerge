import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";
import { DocumentListPage } from "@/pages/DocumentList";
import { useDocuments, type DocumentRow } from "@/stores/documents";
import { useProjects, type Project } from "@/stores/projects";
import { useReadiness } from "@/stores/readiness";
import { useReview } from "@/stores/review";
import type { APIReadinessOut } from "@/types/readiness";
import type { ReviewQueueOut } from "@/types/review";

vi.mock("@/components/ReadinessPanel", () => ({
  ReadinessPanel: () => <section data-testid="readiness-panel" />,
}));

vi.mock("@/components/ReviewInboxBanner", () => ({
  ReviewInboxBanner: () => <section data-testid="review-inbox-banner" />,
}));

const READINESS_STUB: APIReadinessOut = {
  quality_estimate: {
    score: 0,
    judge_component: 0,
    judge_precision: 0,
    ci_low: 0,
    ci_high: 0,
    observation_count: 0,
    vibe_check_size: 0,
  },
  evidence_coverage: {
    annotated_docs: 0,
    annotated_entities: 0,
    annotated_fields: 0,
    field_evidence_fields: 0,
    field_evidence_coverage_ratio: 0,
  },
  schema_maturity: {
    status: "draft",
    annotated_docs: 0,
    annotated_entities: 0,
    recent_schema_breaking_changes: 0,
    message: "",
  },
  regression_health: {
    counterexamples_total: 0,
    counterexample_component: null,
    status: "no_production_feedback",
  },
  risky_fields: [],
  publish_blockers: [],
  warnings: [],
};

const REVIEW_STUB: ReviewQueueOut = {
  required_review: [],
  spot_check: [],
  all: [],
  schema_locked: true,
};

const STALE_READINESS: APIReadinessOut = {
  ...READINESS_STUB,
  evidence_coverage: {
    ...READINESS_STUB.evidence_coverage,
    annotated_docs: 4,
  },
};

const STALE_REVIEW: ReviewQueueOut = {
  required_review: [
    {
      id: 999,
      filename: "previous-project.pdf",
      flagged_fields: ["total"],
    },
  ],
  spot_check: [],
  all: [],
  schema_locked: true,
};

const PROJECT_STUB: Project = {
  id: 7,
  workspace_id: 1,
  name: "Receipts",
  project_type: "receipts",
  template_id: null,
  active_version_id: 11,
  published_version_id: null,
  api_code: null,
  api_published_at: null,
  created_at: "2026-05-04T09:00:00Z",
  created_by: 1,
};

function mockGet(handler?: (url: string) => unknown) {
  return vi.spyOn(api, "get").mockImplementation((url: string) => {
    if (url.endsWith("/readiness")) {
      return Promise.resolve({ data: READINESS_STUB });
    }
    if (url.endsWith("/review-queue")) {
      return Promise.resolve({ data: REVIEW_STUB });
    }
    if (url === "/api/v1/projects/7") {
      return Promise.resolve({ data: PROJECT_STUB });
    }
    if (handler) {
      const data = handler(url);
      if (data !== undefined) return Promise.resolve({ data });
    }
    return Promise.resolve({ data: [] });
  });
}

const UPLOADED: DocumentRow = {
  id: 101,
  project_id: 7,
  filename: "receipt-001.pdf",
  mime_type: "application/pdf",
  page_count: 0,
  byte_size: 12345,
  status: "uploaded",
  created_at: "2026-05-04T10:00:00Z",
};

const EXTRACTED: DocumentRow = {
  id: 102,
  project_id: 7,
  filename: "receipt-002.pdf",
  mime_type: "application/pdf",
  page_count: 1,
  byte_size: 22222,
  status: "extracted",
  created_at: "2026-05-04T11:00:00Z",
};

const PREVIOUS_PROJECT_EXTRACTED: DocumentRow = {
  id: 901,
  project_id: 6,
  filename: "previous-project.pdf",
  mime_type: "application/pdf",
  page_count: 1,
  byte_size: 11111,
  status: "extracted",
  created_at: "2026-05-03T11:00:00Z",
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/projects/7"]}>
      <Routes>
        <Route path="/projects/:id" element={<DocumentListPage />} />
        <Route
          path="/projects/:id/studio/:did"
          element={<div>studio-routed</div>}
        />
      </Routes>
    </MemoryRouter>,
  );
}

async function settle() {
  // Drain trailing useEffect → load() chain so async setState doesn't fire
  // outside act() at test teardown.
  await waitFor(() => {
    const s = useDocuments.getState();
    expect(s.loading).toBe(false);
    expect(s.uploading).toBe(false);
    expect(s.extracting).toBe(false);
    expect(useReadiness.getState().loading).toBe(false);
    expect(useReview.getState().loading).toBe(false);
    expect(useProjects.getState().loading).toBe(false);
  });
}

describe("DocumentListPage", () => {
  beforeEach(() => {
    useDocuments.setState({
      rows: [UPLOADED, EXTRACTED],
      loading: false,
      extracting: false,
      uploading: false,
      error: null,
    });
    useReadiness.setState({ data: READINESS_STUB, loading: false, error: null });
    useReview.setState({ data: REVIEW_STUB, loading: false, error: null });
    useProjects.setState({
      rows: [PROJECT_STUB],
      loading: false,
      error: null,
    });
    mockGet(() => [UPLOADED, EXTRACTED]);
  });
  afterEach(() => {
    vi.restoreAllMocks();
    useDocuments.setState({
      rows: [],
      loading: false,
      extracting: false,
      uploading: false,
      error: null,
    });
    useReadiness.setState({ data: null, loading: false, error: null });
    useReview.setState({ data: null, loading: false, error: null });
    useProjects.setState({
      rows: [],
      loading: false,
      error: null,
    });
  });

  it("renders filename and status for each row", async () => {
    renderPage();
    await settle();
    expect(
      await screen.findByTestId("project-journey-stepper"),
    ).toBeInTheDocument();
    expect(screen.getByText("receipt-001.pdf")).toBeInTheDocument();
    expect(screen.getByText("receipt-002.pdf")).toBeInTheDocument();
    expect(screen.getByText("Uploaded")).toBeInTheDocument();
    expect(screen.getByText("Draft ready")).toBeInTheDocument();
    expect(screen.queryByText("extracted")).not.toBeInTheDocument();
  });

  it("does not use stale previous-project readiness or review data for the journey", async () => {
    useReadiness.setState({
      data: STALE_READINESS,
      loading: false,
      error: null,
    });
    useReview.setState({ data: STALE_REVIEW, loading: false, error: null });

    renderPage();

    const reviewButton = screen.getByRole("button", {
      name: /review examples/i,
    });
    expect(reviewButton).toBeDisabled();
    fireEvent.click(reviewButton);
    expect(screen.queryByText("studio-routed")).not.toBeInTheDocument();

    await settle();
    expect(reviewButton).toBeEnabled();
  });

  it("does not use stale previous-project document rows for the journey", async () => {
    vi.restoreAllMocks();
    useDocuments.setState({
      rows: [PREVIOUS_PROJECT_EXTRACTED],
      loading: false,
      extracting: false,
      uploading: false,
      error: null,
    });
    mockGet(() => []);

    renderPage();

    expect(
      screen.getByRole("button", { name: /extract drafts/i }),
    ).toBeDisabled();
    expect(screen.queryByText("previous-project.pdf")).not.toBeInTheDocument();
  });

  it("does not use late previous-project readiness or review responses for the journey", async () => {
    let resolveReadiness6: (value: { data: APIReadinessOut }) => void = () => {};
    let resolveReview6: (value: { data: ReviewQueueOut }) => void = () => {};
    const readiness6 = new Promise<{ data: APIReadinessOut }>((resolve) => {
      resolveReadiness6 = resolve;
    });
    const review6 = new Promise<{ data: ReviewQueueOut }>((resolve) => {
      resolveReview6 = resolve;
    });

    const get = vi.spyOn(api, "get").mockImplementation((url: string) => {
      if (url === "/api/v1/projects/6/readiness") return readiness6;
      if (url === "/api/v1/projects/6/review-queue") return review6;
      if (url === "/api/v1/projects/7/readiness") {
        return Promise.resolve({ data: READINESS_STUB });
      }
      if (url === "/api/v1/projects/7/review-queue") {
        return Promise.resolve({ data: REVIEW_STUB });
      }
      if (url === "/api/v1/projects/7") {
        return Promise.resolve({ data: PROJECT_STUB });
      }
      return Promise.resolve({ data: [UPLOADED, EXTRACTED] });
    });

    const staleReadinessLoad = useReadiness.getState().load(6);
    const staleReviewLoad = useReview.getState().load(6);

    renderPage();
    await settle();

    resolveReadiness6({ data: STALE_READINESS });
    resolveReview6({ data: STALE_REVIEW });
    await staleReadinessLoad;
    await staleReviewLoad;

    fireEvent.click(screen.getByRole("button", { name: /review examples/i }));
    expect(screen.queryByText("studio-routed")).not.toBeInTheDocument();
    expect(get).toHaveBeenCalledWith("/api/v1/projects/7/review-queue");
  });

  it("clicking a row navigates to /projects/:id/studio/:did", async () => {
    renderPage();
    await settle();
    fireEvent.click(screen.getByText("receipt-001.pdf"));
    expect(await screen.findByText("studio-routed")).toBeInTheDocument();
  });

  it("upload POSTs FormData without manual Content-Type and re-fetches list", async () => {
    const post = vi.spyOn(api, "post").mockResolvedValue({ data: [UPLOADED] });

    renderPage();
    await settle();
    const file = new File(["x"], "new.pdf", { type: "application/pdf" });
    const input = screen.getByTestId(
      "document-upload-input",
    ) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => expect(post).toHaveBeenCalledTimes(1));
    expect(post).toHaveBeenCalledWith(
      "/api/v1/projects/7/documents",
      expect.any(FormData),
    );
    // Axios sets the Content-Type with the multipart boundary itself; the
    // store must NOT pass a manual Content-Type header (would strip boundary).
    expect(post.mock.calls[0]).toHaveLength(2);
    const fd = post.mock.calls[0]![1] as FormData;
    expect(fd.getAll("files")).toHaveLength(1);
    await settle();
  });

  it("extract button POSTs and re-fetches list afterwards", async () => {
    const post = vi.spyOn(api, "post").mockResolvedValue({ data: "ok" });

    renderPage();
    await settle();
    fireEvent.click(screen.getByRole("button", { name: /re-extract/i }));

    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post).toHaveBeenCalledWith("/api/v1/projects/7/extract");
    await settle();
  });

  it("upload + extract trigger readiness + review-queue refresh", async () => {
    // R8.7 hygiene-tail: ReadinessPanel + ReviewInboxBanner used to
    // display stale state ("0 docs total") right after a fresh upload
    // or extract until the user reloaded. The documents store now
    // fires both stores' load() in fire-and-forget mode after each
    // mutation; pin both code paths.
    const post = vi.spyOn(api, "post").mockResolvedValue({ data: [UPLOADED] });
    const get = mockGet(() => [UPLOADED, EXTRACTED]);

    renderPage();
    await settle();

    const file = new File(["x"], "new.pdf", { type: "application/pdf" });
    const input = screen.getByTestId(
      "document-upload-input",
    ) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });
    await waitFor(() => expect(post).toHaveBeenCalledTimes(1));
    await settle();

    fireEvent.click(screen.getByRole("button", { name: /re-extract/i }));
    await waitFor(() => expect(post).toHaveBeenCalledTimes(2));
    await settle();

    const urls = get.mock.calls.map((c) => c[0] as string);
    // Both readiness and review-queue should be hit at least twice
    // (initial mount + after upload + after extract = at least 2 each).
    expect(
      urls.filter((u) => u.endsWith("/readiness")).length,
    ).toBeGreaterThanOrEqual(2);
    expect(
      urls.filter((u) => u.endsWith("/review-queue")).length,
    ).toBeGreaterThanOrEqual(2);
  });

  it("empty state shows helper copy", async () => {
    vi.restoreAllMocks();
    useDocuments.setState({
      rows: [],
      loading: false,
      extracting: false,
      uploading: false,
      error: null,
    });
    mockGet(() => []);
    renderPage();
    await settle();
    expect(screen.getByText(/no documents yet/i)).toBeInTheDocument();
  });
});
