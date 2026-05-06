import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import { ApiConsolePage } from "@/pages/ApiConsole";
import { useProjects, type Project } from "@/stores/projects";
import { useReadiness } from "@/stores/readiness";
import type { APIReadinessOut } from "@/types/readiness";

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

const PROJECT: Project = {
  id: 1,
  workspace_id: 1,
  name: "JR demo",
  project_type: "extraction",
  template_id: null,
  active_version_id: 7,
  published_version_id: 5,
  api_code: "japan-receipts",
  api_published_at: "2026-05-04T00:00:00Z",
  created_at: "2026-05-01T00:00:00Z",
  created_by: 1,
};

const VERSIONS = [
  { id: 7, project_id: 1, version_number: 3, locked: false },
  { id: 5, project_id: 1, version_number: 2, locked: true },
  { id: 3, project_id: 1, version_number: 1, locked: true },
];

const KEYS = [
  {
    id: 9,
    prefix: "ek_abc",
    name: "default",
    last_used_at: null,
    created_at: "2026-05-04T00:00:00Z",
  },
];

function renderConsole() {
  return render(
    <ToastProvider>
      <MemoryRouter initialEntries={["/projects/1/api-console"]}>
        <Routes>
          <Route path="/projects/:id/api-console" element={<ApiConsolePage />} />
        </Routes>
      </MemoryRouter>
    </ToastProvider>,
  );
}

async function settle() {
  await waitFor(() => expect(useProjects.getState().loading).toBe(false));
}

function mockGets(opts?: {
  versions?: typeof VERSIONS;
  keys?: typeof KEYS;
  project?: Project;
}) {
  vi.spyOn(api, "get").mockImplementation((url: string) => {
    if (url.endsWith("/readiness"))
      return Promise.resolve({ data: READINESS_STUB });
    if (url.endsWith("/versions"))
      return Promise.resolve({ data: opts?.versions ?? VERSIONS });
    if (url.endsWith("/api-keys"))
      return Promise.resolve({ data: opts?.keys ?? KEYS });
    if (url.endsWith("/contract-diff") || url.includes("/contract-diff?"))
      return Promise.resolve({
        data: {
          from_version_id: 5,
          to_version_id: 7,
          has_breaking_changes: true,
          items: [
            {
              kind: "field_removed",
              severity: "breaking",
              field_name: "tax_id",
              before: null,
              after: null,
              message: "field 'tax_id' removed",
            },
            {
              kind: "description_changed",
              severity: "non_breaking",
              field_name: "total",
              before: null,
              after: null,
              message: "description changed for 'total'",
            },
          ],
        },
      });
    return Promise.resolve({ data: opts?.project ?? PROJECT });
  });
}

describe("ApiConsolePage", () => {
  beforeEach(() => {
    useProjects.setState({
      rows: [PROJECT],
      apiKeys: KEYS,
      contractDiff: null,
      loading: false,
      error: null,
    });
    useReadiness.setState({ data: READINESS_STUB, loading: false, error: null });
    mockGets();
  });
  afterEach(() => {
    vi.restoreAllMocks();
    useProjects.setState({
      rows: [],
      apiKeys: [],
      contractDiff: null,
      loading: false,
      error: null,
    });
    useReadiness.setState({ data: null, loading: false, error: null });
  });

  it("renders distinct Production and Lab version pointer cards", async () => {
    renderConsole();
    await settle();
    const production = await screen.findByTestId("production-pointer");
    const lab = await screen.findByTestId("lab-pointer");
    expect(within(production).getByText(/v2/i)).toBeInTheDocument();
    expect(within(lab).getByText(/v3/i)).toBeInTheDocument();
  });

  it("renders contract diff items with severity badges", async () => {
    renderConsole();
    await settle();
    expect(
      await screen.findByText(/field 'tax_id' removed/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/description changed for 'total'/i),
    ).toBeInTheDocument();
  });

  it("Contract diff swaps to initial-publish copy when from_version_id is null", async () => {
    // Dogfood follow-up #6: a first publish has no prior version, so
    // "Activating this version will break existing integrators" is noise.
    vi.spyOn(api, "get").mockImplementation((url: string) => {
      if (url.endsWith("/readiness"))
        return Promise.resolve({ data: READINESS_STUB });
      if (url.endsWith("/versions"))
        return Promise.resolve({ data: VERSIONS });
      if (url.endsWith("/api-keys"))
        return Promise.resolve({ data: KEYS });
      if (url.endsWith("/contract-diff") || url.includes("/contract-diff?"))
        return Promise.resolve({
          data: {
            from_version_id: null,
            to_version_id: 7,
            // Items are technically "breaking" against an empty prior, but
            // for an initial publish that's noise dressed as alarms.
            has_breaking_changes: true,
            items: [
              {
                kind: "required_field_added",
                severity: "breaking",
                field_name: "shop_name",
                before: null,
                after: { name: "shop_name", type: "string" },
                message: "required field 'shop_name' added",
              },
            ],
          },
        });
      return Promise.resolve({ data: PROJECT });
    });

    renderConsole();
    await settle();
    expect(
      screen.queryByText(/will break existing integrators/i),
    ).not.toBeInTheDocument();
    expect(
      await screen.findByText(/initial contract — no prior version/i),
    ).toBeInTheDocument();
  });

  it("Activate-for-API button is disabled when active version is unlocked", async () => {
    renderConsole();
    await settle();
    const activate = await screen.findByRole("button", {
      name: /activate for api/i,
    });
    expect(activate).toBeDisabled();
  });

  it("Activate-for-API enables when active version is locked", async () => {
    mockGets({
      versions: [
        { id: 7, project_id: 1, version_number: 3, locked: true },
        { id: 5, project_id: 1, version_number: 2, locked: true },
      ],
    });
    renderConsole();
    await settle();
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /activate for api/i }),
      ).not.toBeDisabled();
    });
  });

  it("Create key opens the reveal modal showing the plaintext key", async () => {
    vi.spyOn(api, "post").mockResolvedValue({
      data: {
        id: 12,
        prefix: "ek_xyz",
        name: "default",
        key: "ek_xyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
      },
    });

    renderConsole();
    await settle();

    fireEvent.click(
      await screen.findByRole("button", { name: /create key/i }),
    );

    expect(
      await screen.findByText("ek_xyzABCDEFGHIJKLMNOPQRSTUVWXYZ"),
    ).toBeInTheDocument();
  });

  it("Revoke now requires a confirmation click and removes the row + shows toast", async () => {
    // Dogfood follow-up #5: clicking the row's Revoke button must NOT
    // delete the key directly; it opens a Radix Dialog with the key name
    // interpolated. Only after clicking the dialog's primary "Revoke"
    // button should the network DELETE fire and the row disappear.
    const del = vi.spyOn(api, "delete").mockResolvedValue({
      data: { ...KEYS[0]! },
    });

    renderConsole();
    await settle();
    expect(await screen.findByText("ek_abc")).toBeInTheDocument();

    // Open the confirmation dialog.
    fireEvent.click(
      screen.getByRole("button", { name: /^revoke$/i }),
    );
    // Radix AlertDialog gives us role="alertdialog" — scope all
    // subsequent queries inside it instead of relying on positional
    // ordering of duplicate "Revoke" labels.
    const dialog = await screen.findByRole("alertdialog");
    expect(within(dialog).getByText(/revoke key 'default'/i)).toBeInTheDocument();
    expect(del).not.toHaveBeenCalled();
    fireEvent.click(within(dialog).getByRole("button", { name: /^revoke$/i }));

    await waitFor(() =>
      expect(screen.queryByText("ek_abc")).not.toBeInTheDocument(),
    );
    expect(del).toHaveBeenCalled();

    const viewport = await screen.findByTestId("toast-viewport");
    expect(viewport.textContent ?? "").toMatch(/saved/i);
  });

  it("renders the read-only feedback example block on every load", async () => {
    renderConsole();
    await settle();
    // The summary text is always present, even if the form is gated.
    expect(
      await screen.findByText(/partial feedback example/i),
    ).toBeInTheDocument();
  });

  it("hides the interactive feedback form when no API keys exist", async () => {
    mockGets({ keys: [] });
    useProjects.setState({
      rows: [PROJECT],
      apiKeys: [],
      contractDiff: null,
      loading: false,
      error: null,
    });
    renderConsole();
    await settle();
    expect(
      await screen.findByText(/create an api key above before sending test feedback/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /send test feedback/i }),
    ).not.toBeInTheDocument();
  });

  it("shows the interactive feedback form when at least one API key exists", async () => {
    renderConsole();
    await settle();
    // KEYS array (default) has one entry, so the form must mount.
    expect(
      await screen.findByRole("button", { name: /send test feedback/i }),
    ).toBeInTheDocument();
    // The gating message must NOT appear at the same time.
    expect(
      screen.queryByText(/create an api key above before sending test feedback/i),
    ).not.toBeInTheDocument();
  });
});
