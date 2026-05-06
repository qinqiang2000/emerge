import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ReviewInboxBanner } from "@/components/ReviewInboxBanner";
import { api } from "@/lib/api";
import { ReviewInboxPage } from "@/pages/ReviewInbox";
import { useReview } from "@/stores/review";
import type { ReviewQueueOut } from "@/types/review";

const EMPTY_QUEUE: ReviewQueueOut = {
  required_review: [],
  spot_check: [],
  all: [],
  schema_locked: true,
};

const SAMPLE_QUEUE: ReviewQueueOut = {
  required_review: [
    { id: 11, filename: "needs_review_a.pdf", flagged_fields: ["total", "tax_id"] },
    { id: 12, filename: "needs_review_b.pdf", flagged_fields: ["currency"] },
  ],
  spot_check: [
    { id: 21, filename: "spot_a.pdf", flagged_fields: [] },
  ],
  all: [
    { id: 11, filename: "needs_review_a.pdf", flagged_fields: ["total", "tax_id"] },
    { id: 12, filename: "needs_review_b.pdf", flagged_fields: ["currency"] },
    { id: 21, filename: "spot_a.pdf", flagged_fields: [] },
    { id: 22, filename: "all_only.pdf", flagged_fields: [] },
  ],
  schema_locked: true,
};

function mockQueue(payload: ReviewQueueOut = SAMPLE_QUEUE) {
  vi.spyOn(api, "get").mockResolvedValue({ data: payload });
}

function PathProbe() {
  const { pathname } = useLocation();
  return <div data-testid="probe">{pathname}</div>;
}

function renderBannerAt(initialPath: string) {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route
          path="/projects/:id"
          element={<ReviewInboxBanner projectId={7} />}
        />
        <Route
          path="/projects/:id/studio/:did"
          element={<PathProbe />}
        />
        <Route
          path="/projects/:id/review"
          element={<PathProbe />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

function renderPageAt(initialPath: string) {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route
          path="/projects/:id/review"
          element={<ReviewInboxPage />}
        />
        <Route
          path="/projects/:id/studio/:did"
          element={<PathProbe />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

async function settleReview() {
  await waitFor(() => expect(useReview.getState().loading).toBe(false));
}

describe("ReviewInboxBanner", () => {
  beforeEach(() => {
    useReview.setState({ data: null, loading: false, error: null });
  });
  afterEach(() => {
    vi.restoreAllMocks();
    useReview.setState({ data: null, loading: false, error: null });
  });

  it("renders three counts pulled from the review queue", async () => {
    mockQueue();
    renderBannerAt("/projects/7");
    await settleReview();
    const banner = await screen.findByTestId("review-inbox-banner");
    // required_review = 2, spot_check = 1, all = 4
    expect(within(banner).getByTestId("review-required-count").textContent).toMatch(/\b2\b/);
    expect(within(banner).getByTestId("review-spot-check-count").textContent).toMatch(/\b1\b/);
    expect(within(banner).getByTestId("review-all-count").textContent).toMatch(/\b4\b/);
  });

  it("Review next navigates to first required_review item's Studio", async () => {
    mockQueue();
    renderBannerAt("/projects/7");
    await settleReview();
    const button = await screen.findByRole("button", { name: /review next/i });
    expect(button).not.toBeDisabled();
    fireEvent.click(button);
    expect(screen.getByTestId("probe").textContent).toBe("/projects/7/studio/11");
  });

  it("falls back to first spot_check when required_review is empty", async () => {
    mockQueue({
      required_review: [],
      spot_check: [{ id: 31, filename: "spot.pdf", flagged_fields: [] }],
      all: [{ id: 31, filename: "spot.pdf", flagged_fields: [] }],
      schema_locked: true,
    });
    renderBannerAt("/projects/7");
    await settleReview();
    const button = await screen.findByRole("button", { name: /review next/i });
    expect(button).not.toBeDisabled();
    fireEvent.click(button);
    expect(screen.getByTestId("probe").textContent).toBe("/projects/7/studio/31");
  });

  it("disables Review next and shows 'waiting on the judge' when docs exist but no verdicts", async () => {
    mockQueue({
      required_review: [],
      spot_check: [],
      all: [
        { id: 41, filename: "ok.pdf", flagged_fields: [] },
      ],
      schema_locked: true,
    });
    renderBannerAt("/projects/7");
    await settleReview();
    const banner = await screen.findByTestId("review-inbox-banner");
    // Pre-judge "all caught up" copy was misleading — now we ask the user
    // to actually run the judge.
    expect(within(banner).getByText(/waiting on the judge|run.*judge/i)).toBeInTheDocument();
    expect(within(banner).queryByText(/all caught up/i)).not.toBeInTheDocument();
    expect(within(banner).queryByText(/0\s*of\s*0/i)).not.toBeInTheDocument();
    const button = within(banner).getByRole("button", { name: /review next/i });
    expect(button).toBeDisabled();
  });

  it("shows 'all caught up' only when the judge has run (spot_check populated) and required is empty", async () => {
    mockQueue({
      required_review: [],
      spot_check: [{ id: 51, filename: "clean.pdf", flagged_fields: [] }],
      all: [{ id: 51, filename: "clean.pdf", flagged_fields: [] }],
      schema_locked: true,
    });
    renderBannerAt("/projects/7");
    await settleReview();
    // With spot_check non-empty, queueEmpty is false → no banner-level empty
    // message at all (counts speak for themselves). This is correct: the
    // "all caught up" callout only appears when both sections are empty.
    const banner = await screen.findByTestId("review-inbox-banner");
    expect(within(banner).queryByTestId("review-all-caught-up")).not.toBeInTheDocument();
  });

  it("renders 'empty pool' when no docs exist at all", async () => {
    mockQueue(EMPTY_QUEUE);
    renderBannerAt("/projects/7");
    await settleReview();
    const banner = await screen.findByTestId("review-inbox-banner");
    expect(banner.textContent ?? "").not.toMatch(/0\s*of\s*0/i);
    expect(within(banner).getByText(/no documents in the vibe-check pool|extract.*to start/i)).toBeInTheDocument();
  });

  it("clears stale data when switching projects (no flash of previous counts)", async () => {
    useReview.setState({
      data: {
        required_review: [
          { id: 99, filename: "stale.pdf", flagged_fields: ["stale_field"] },
        ],
        spot_check: [],
        all: [{ id: 99, filename: "stale.pdf", flagged_fields: ["stale_field"] }],
        schema_locked: true,
      },
      loading: false,
      error: null,
    });
    let resolveLoad: (v: unknown) => void = () => {};
    const pending = new Promise((resolve) => {
      resolveLoad = resolve;
    });
    vi.spyOn(api, "get").mockReturnValue(
      pending as unknown as ReturnType<typeof api.get>,
    );
    renderBannerAt("/projects/8");
    await waitFor(() => expect(useReview.getState().loading).toBe(true));
    expect(screen.queryByText("stale.pdf")).not.toBeInTheDocument();
    expect(screen.queryByText(/\b99\b/)).not.toBeInTheDocument();
    resolveLoad({ data: EMPTY_QUEUE });
    await waitFor(() => expect(useReview.getState().loading).toBe(false));
  });

  it("uses only semantic Tailwind tokens (no raw color classes)", async () => {
    mockQueue();
    const { container } = renderBannerAt("/projects/7");
    await settleReview();
    const html = container.innerHTML;
    expect(html).not.toMatch(/\bbg-(?:gray|white|black)\b/);
    expect(html).not.toMatch(/\btext-(?:white|black)\b/);
    expect(html).not.toMatch(/\btext-gray-\d+\b/);
  });
});

describe("ReviewInboxPage", () => {
  beforeEach(() => {
    useReview.setState({ data: null, loading: false, error: null });
  });
  afterEach(() => {
    vi.restoreAllMocks();
    useReview.setState({ data: null, loading: false, error: null });
  });

  it("renders three sections (Required review, Spot-check, All) with the right ids", async () => {
    mockQueue();
    renderPageAt("/projects/7/review");
    await settleReview();
    const required = await screen.findByTestId("review-section-required");
    const spot = screen.getByTestId("review-section-spot-check");
    const all = screen.getByTestId("review-section-all");
    expect(within(required).getByText("needs_review_a.pdf")).toBeInTheDocument();
    expect(within(required).getByText("needs_review_b.pdf")).toBeInTheDocument();
    expect(within(spot).getByText("spot_a.pdf")).toBeInTheDocument();
    expect(within(all).getByText("all_only.pdf")).toBeInTheDocument();
  });

  it("each row renders flagged_fields as chips when present", async () => {
    mockQueue();
    renderPageAt("/projects/7/review");
    await settleReview();
    const required = await screen.findByTestId("review-section-required");
    expect(within(required).getByText("total")).toBeInTheDocument();
    expect(within(required).getByText("tax_id")).toBeInTheDocument();
    expect(within(required).getByText("currency")).toBeInTheDocument();
  });

  it("clicking a row navigates to Studio for that document", async () => {
    mockQueue();
    renderPageAt("/projects/7/review");
    await settleReview();
    const row = await screen.findByTestId("review-row-required-12");
    fireEvent.click(row);
    expect(screen.getByTestId("probe").textContent).toBe("/projects/7/studio/12");
  });

  it("renders empty-state copy per section when that bucket is empty", async () => {
    mockQueue({
      required_review: [],
      spot_check: [],
      all: [
        { id: 51, filename: "ok.pdf", flagged_fields: [] },
      ],
      schema_locked: true,
    });
    renderPageAt("/projects/7/review");
    await settleReview();
    const required = await screen.findByTestId("review-section-required");
    const spot = screen.getByTestId("review-section-spot-check");
    expect(
      within(required).getByText(/all caught up|no flagged|nothing/i),
    ).toBeInTheDocument();
    expect(
      within(spot).getByText(/no spot-check|all caught up|nothing/i),
    ).toBeInTheDocument();
  });

  it("renders the Draft-mode callout when schema_locked is false", async () => {
    mockQueue({ ...SAMPLE_QUEUE, schema_locked: false });
    renderPageAt("/projects/7/review");
    await settleReview();
    const callout = await screen.findByTestId("review-draft-mode-callout");
    expect(callout.textContent ?? "").toMatch(/Draft/i);
    expect(callout.textContent ?? "").toMatch(/lock/i);
  });

  it("hides the Draft-mode callout when schema_locked is true", async () => {
    mockQueue({ ...SAMPLE_QUEUE, schema_locked: true });
    renderPageAt("/projects/7/review");
    await settleReview();
    expect(
      screen.queryByTestId("review-draft-mode-callout"),
    ).not.toBeInTheDocument();
  });

  it("surfaces translated error envelope when load fails", async () => {
    vi.spyOn(api, "get").mockRejectedValue(
      new (await import("@/lib/api")).EmergeError(
        "FORBIDDEN",
        "no",
        403,
      ),
    );
    renderPageAt("/projects/7/review");
    await waitFor(() => expect(useReview.getState().loading).toBe(false));
    expect(useReview.getState().error).toBe("errors.FORBIDDEN");
    expect(
      screen.getByRole("alert").textContent ?? "",
    ).toMatch(/permission|sign in|forbidden/i);
  });
});

describe("useReview store", () => {
  beforeEach(() => {
    useReview.setState({ data: null, loading: false, error: null });
  });
  afterEach(() => {
    vi.restoreAllMocks();
    useReview.setState({ data: null, loading: false, error: null });
  });

  it("calls /api/v1/projects/:id/review-queue and stores the response", async () => {
    const get = vi.spyOn(api, "get").mockResolvedValue({ data: SAMPLE_QUEUE });
    await useReview.getState().load(99);
    expect(get).toHaveBeenCalledWith("/api/v1/projects/99/review-queue");
    expect(useReview.getState().data).toEqual(SAMPLE_QUEUE);
    expect(useReview.getState().loading).toBe(false);
  });
});
