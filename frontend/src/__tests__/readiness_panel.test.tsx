import { render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ReadinessPanel } from "@/components/ReadinessPanel";
import { api } from "@/lib/api";
import { useReadiness } from "@/stores/readiness";
import type { APIReadinessOut } from "@/types/readiness";

const BASE_READINESS: APIReadinessOut = {
  quality_estimate: {
    score: 0.6,
    judge_component: 0.86,
    judge_precision: 0.86,
    ci_low: 0.78,
    ci_high: 0.94,
    observation_count: 28,
    vibe_check_size: 12,
  },
  evidence_coverage: {
    reviewed_docs: 12,
    reviewed_entities: 48,
    reviewed_fields: 134,
    field_evidence_fields: 83,
    field_evidence_coverage_ratio: 0.62,
  },
  schema_maturity: {
    status: "lock_candidate",
    reviewed_docs: 12,
    reviewed_entities: 48,
    recent_schema_breaking_changes: 0,
    message: "Schema ready to lock. Confirm evidence coverage first.",
  },
  regression_health: {
    counterexamples_total: 0,
    counterexample_component: null,
    status: "no_production_feedback",
  },
  risky_fields: [],
  publish_blockers: [],
  warnings: ["no_production_feedback"],
};

function mockReadiness(overrides: Partial<APIReadinessOut> = {}) {
  vi.spyOn(api, "get").mockResolvedValue({
    data: { ...BASE_READINESS, ...overrides },
  });
}

async function renderPanel() {
  const r = render(<ReadinessPanel projectId={42} />);
  await waitFor(() => expect(useReadiness.getState().loading).toBe(false));
  return r;
}

describe("ReadinessPanel", () => {
  beforeEach(() => {
    useReadiness.setState({ data: null, loading: false, error: null });
  });
  afterEach(() => {
    vi.restoreAllMocks();
    useReadiness.setState({ data: null, loading: false, error: null });
  });

  it("never renders 100% when counterexamples_total === 0", async () => {
    mockReadiness();
    const { container } = await renderPanel();
    expect(container.textContent ?? "").not.toMatch(/100\s*%/);
    const regression = await screen.findByTestId("readiness-regression");
    expect(
      within(regression).getByText(/no production feedback yet/i),
    ).toBeInTheDocument();
    // The dedicated "no feedback" callout also visible
    expect(screen.getByTestId("readiness-no-feedback")).toBeInTheDocument();
  });

  it("hides the prior-only quality number when observation_count is 0 (no false signal)", async () => {
    mockReadiness({
      quality_estimate: {
        score: 0.8,
        judge_component: 0.8,
        judge_precision: 0.8,
        ci_low: 0.57,
        ci_high: 1.0,
        observation_count: 0,
        vibe_check_size: 3,
      },
      risky_fields: [],
    });
    await renderPanel();
    const quality = await screen.findByTestId("readiness-quality");
    // The Bayesian prior would render as "80% ± 23%" — must not show on N=0.
    expect(within(quality).queryByText(/80\s*%/)).not.toBeInTheDocument();
    expect(within(quality).queryByText(/±/)).not.toBeInTheDocument();
    expect(
      within(quality).getByText(/awaiting first verdict|no signal/i),
    ).toBeInTheDocument();
    // The obs/vibe-check meta is still shown so the user understands why.
    expect(within(quality).getByText(/0\s*obs/i)).toBeInTheDocument();
  });

  it("uses 'no verdicts yet' copy for risky fields when observation_count is 0", async () => {
    mockReadiness({
      quality_estimate: {
        score: 0.8,
        judge_component: 0.8,
        judge_precision: 0.8,
        ci_low: 0.57,
        ci_high: 1.0,
        observation_count: 0,
        vibe_check_size: 3,
      },
      risky_fields: [],
    });
    await renderPanel();
    const rf = await screen.findByTestId("readiness-risky");
    expect(
      within(rf).getByText(/no verdicts yet|risky fields appear after the judge/i),
    ).toBeInTheDocument();
    // The "all clean" reading must NOT appear when we haven't measured anything.
    expect(within(rf).queryByText(/no risky fields detected/i)).not.toBeInTheDocument();
  });

  it("renders quality CI band as point% ± half% with obs and vibe-check counts", async () => {
    mockReadiness();
    await renderPanel();
    const quality = await screen.findByTestId("readiness-quality");
    // judge_precision 0.86 → 86%; (ci_high - ci_low)/2 = 0.08 → 8%
    expect(within(quality).getByText(/86\s*%/)).toBeInTheDocument();
    expect(within(quality).getByText(/±/)).toBeInTheDocument();
    expect(within(quality).getByText(/8\s*%/)).toBeInTheDocument();
    expect(within(quality).getByText(/28/)).toBeInTheDocument();
    expect(within(quality).getByText(/12/)).toBeInTheDocument();
  });

  it("renders evidence counts and coverage ratio", async () => {
    mockReadiness();
    await renderPanel();
    const ev = await screen.findByTestId("readiness-evidence");
    expect(within(ev).getByText(/12/)).toBeInTheDocument();
    expect(within(ev).getByText(/48/)).toBeInTheDocument();
    expect(within(ev).getByText(/134/)).toBeInTheDocument();
    expect(within(ev).getByText(/62\s*%/)).toBeInTheDocument();
  });

  it("renders schema maturity using translated status, never raw slug", async () => {
    mockReadiness();
    await renderPanel();
    const m = await screen.findByTestId("readiness-maturity");
    // raw slug must not leak
    expect(within(m).queryByText(/lock_candidate/i)).not.toBeInTheDocument();
    expect(
      within(m).getByText(/lock candidate|ready to lock/i),
    ).toBeInTheDocument();
  });

  it("renders top 5 risky fields with +N more affordance for excess", async () => {
    mockReadiness({
      risky_fields: [
        { field_name: "tax_id", count: 7 },
        { field_name: "currency", count: 5 },
        { field_name: "total", count: 4 },
        { field_name: "vendor", count: 3 },
        { field_name: "issue_date", count: 2 },
        { field_name: "po_number", count: 1 },
        { field_name: "tax_rate", count: 1 },
      ],
    });
    await renderPanel();
    const rf = await screen.findByTestId("readiness-risky");
    // top 5 visible
    expect(within(rf).getByText("tax_id")).toBeInTheDocument();
    expect(within(rf).getByText("currency")).toBeInTheDocument();
    expect(within(rf).getByText("total")).toBeInTheDocument();
    expect(within(rf).getByText("vendor")).toBeInTheDocument();
    expect(within(rf).getByText("issue_date")).toBeInTheDocument();
    // 6th + 7th hidden behind "+N more"
    expect(within(rf).queryByText("po_number")).not.toBeInTheDocument();
    expect(within(rf).queryByText("tax_rate")).not.toBeInTheDocument();
    expect(within(rf).getByText(/\+\s*2\s*more/i)).toBeInTheDocument();
  });

  it("renders all top 5 (or fewer) without +N more when count <= 5", async () => {
    mockReadiness({
      risky_fields: [
        { field_name: "tax_id", count: 3 },
        { field_name: "currency", count: 2 },
      ],
    });
    await renderPanel();
    const rf = await screen.findByTestId("readiness-risky");
    expect(within(rf).getByText("tax_id")).toBeInTheDocument();
    expect(within(rf).getByText("currency")).toBeInTheDocument();
    expect(within(rf).queryByText(/more/i)).not.toBeInTheDocument();
  });

  it("translates publish_blockers; never leaks raw slugs to users", async () => {
    mockReadiness({
      publish_blockers: ["empty_schema", "active_version_unlocked"],
      schema_maturity: { ...BASE_READINESS.schema_maturity, status: "draft" },
    });
    await renderPanel();
    const blockers = await screen.findByTestId("readiness-blockers");
    // raw slugs must NEVER reach the user
    expect(within(blockers).queryByText("empty_schema")).not.toBeInTheDocument();
    expect(
      within(blockers).queryByText("active_version_unlocked"),
    ).not.toBeInTheDocument();
    // friendly translated copy is present
    expect(
      within(blockers).getByText(/schema is empty|empty schema/i),
    ).toBeInTheDocument();
    expect(
      within(blockers).getByText(/lab.*not locked|version.*unlocked|lock the schema/i),
    ).toBeInTheDocument();
  });

  it("falls back to humanised slug + console.warn for unknown blocker keys", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    mockReadiness({ publish_blockers: ["future_unknown_slug"] });
    await renderPanel();
    const blockers = await screen.findByTestId("readiness-blockers");
    expect(
      within(blockers).queryByText("future_unknown_slug"),
    ).not.toBeInTheDocument();
    // humanised: "Future unknown slug"
    expect(
      within(blockers).getByText(/future unknown slug/i),
    ).toBeInTheDocument();
    expect(warn).toHaveBeenCalled();
  });

  it("renders regression count when status is measured (passing/failing) and never reads raw status slug", async () => {
    mockReadiness({
      regression_health: {
        counterexamples_total: 8,
        counterexample_component: 0.875,
        status: "passing",
      },
    });
    await renderPanel();
    const reg = await screen.findByTestId("readiness-regression");
    // approximated passing count = round(0.875 * 8) = 7
    expect(within(reg).getByText(/7\s*\/\s*8/)).toBeInTheDocument();
    expect(
      within(reg).queryByText(/no production feedback/i),
    ).not.toBeInTheDocument();
  });

  it("suppresses the passing count when status is 'unknown' (avoids contradicting the 'not yet computed' line)", async () => {
    mockReadiness({
      regression_health: {
        counterexamples_total: 8,
        // backend may report a fallback component while still flagging status=unknown
        counterexample_component: 1.0,
        status: "unknown",
      },
    });
    await renderPanel();
    const reg = await screen.findByTestId("readiness-regression");
    expect(within(reg).queryByText(/8\s*\/\s*8/)).not.toBeInTheDocument();
    expect(within(reg).queryByText(/passing/i)).not.toBeInTheDocument();
    expect(
      within(reg).getByText(/not yet computed|status unknown/i),
    ).toBeInTheDocument();
  });

  it("renders distinct copy for each regression_health.status value", async () => {
    // passing
    mockReadiness({
      regression_health: {
        counterexamples_total: 8,
        counterexample_component: 1.0,
        status: "passing",
      },
    });
    const r1 = await renderPanel();
    const passingText =
      within(r1.getByTestId("readiness-regression")).getByTestId(
        "readiness-regression-status",
      ).textContent ?? "";
    r1.unmount();
    useReadiness.setState({ data: null, loading: false, error: null });

    // failing
    mockReadiness({
      regression_health: {
        counterexamples_total: 8,
        counterexample_component: 0.5,
        status: "failing",
      },
    });
    const r2 = await renderPanel();
    const failingText =
      within(r2.getByTestId("readiness-regression")).getByTestId(
        "readiness-regression-status",
      ).textContent ?? "";
    r2.unmount();
    useReadiness.setState({ data: null, loading: false, error: null });

    // unknown
    mockReadiness({
      regression_health: {
        counterexamples_total: 8,
        counterexample_component: 0.5,
        status: "unknown",
      },
    });
    const r3 = await renderPanel();
    const unknownText =
      within(r3.getByTestId("readiness-regression")).getByTestId(
        "readiness-regression-status",
      ).textContent ?? "";
    r3.unmount();
    useReadiness.setState({ data: null, loading: false, error: null });

    expect(passingText).not.toEqual(failingText);
    expect(passingText).not.toEqual(unknownText);
    expect(failingText).not.toEqual(unknownText);
  });

  it("falls back to 'status not yet computed' when total > 0 but component is null", async () => {
    mockReadiness({
      regression_health: {
        counterexamples_total: 8,
        counterexample_component: null,
        status: "unknown",
      },
    });
    await renderPanel();
    const reg = await screen.findByTestId("readiness-regression");
    // must NOT pretend 0/8 passing when we don't actually know
    expect(within(reg).queryByText(/0\s*\/\s*8/)).not.toBeInTheDocument();
    expect(
      within(reg).getByText(/not yet computed|status unknown/i),
    ).toBeInTheDocument();
  });

  it("clears stale data when load() is called for a new project", async () => {
    // seed a populated state simulating /projects/1
    useReadiness.setState({
      data: {
        ...BASE_READINESS,
        risky_fields: [{ field_name: "stale_field_from_proj_1", count: 9 }],
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
    // render the panel for projectId=2 — load(2) should clear stale data first
    render(<ReadinessPanel projectId={2} />);
    await waitFor(() =>
      expect(useReadiness.getState().loading).toBe(true),
    );
    // While load(2) is in flight, stale project-1 risky field must NOT be shown
    expect(screen.queryByText("stale_field_from_proj_1")).not.toBeInTheDocument();
    // Resolve the in-flight request to drain the act() warning
    resolveLoad({ data: BASE_READINESS });
    await waitFor(() =>
      expect(useReadiness.getState().loading).toBe(false),
    );
  });

  it("uses only semantic Tailwind tokens (no raw color classes)", async () => {
    mockReadiness({
      publish_blockers: ["empty_schema"],
      risky_fields: [{ field_name: "tax_id", count: 3 }],
    });
    const { container } = await renderPanel();
    const html = container.innerHTML;
    // red-line: no raw Tailwind color classes anywhere in the panel
    expect(html).not.toMatch(/\bbg-(?:gray|white|black)\b/);
    expect(html).not.toMatch(/\btext-(?:white|black)\b/);
    // and no raw gray text scale either
    expect(html).not.toMatch(/\btext-gray-\d+\b/);
  });
});
