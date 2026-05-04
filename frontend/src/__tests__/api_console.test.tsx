import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";
import { ApiConsolePage } from "@/pages/ApiConsole";
import { useProjects, type Project } from "@/stores/projects";

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
    <MemoryRouter initialEntries={["/projects/1/api-console"]}>
      <Routes>
        <Route path="/projects/:id/api-console" element={<ApiConsolePage />} />
      </Routes>
    </MemoryRouter>,
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

  it("Revoke removes the key row from the table", async () => {
    vi.spyOn(api, "delete").mockResolvedValue({
      data: { ...KEYS[0]! },
    });

    renderConsole();
    await settle();
    expect(await screen.findByText("ek_abc")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /revoke/i }));
    await waitFor(() =>
      expect(screen.queryByText("ek_abc")).not.toBeInTheDocument(),
    );
  });
});
