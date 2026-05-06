import { act, cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "@/App";
import { ProjectSubNav } from "@/components/ProjectSubNav";
import { useAuth } from "@/stores/auth";

vi.mock("@/pages/ReviewInbox", () => ({
  ReviewInboxPage: () => <div>examples-page</div>,
}));

vi.mock("@/pages/SchemaEditor", () => ({
  SchemaEditorPage: () => <div>rules-page</div>,
}));

vi.mock("@/pages/ApiConsole", () => ({
  ApiConsolePage: () => <div>api-page</div>,
}));

const originalAuthInit = useAuth.getState().init;

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route
          path="/projects/:id"
          element={<ProjectSubNav projectId={7} />}
        />
        <Route
          path="/projects/:id/studio/:did"
          element={<ProjectSubNav projectId={7} />}
        />
        <Route
          path="/projects/:id/examples"
          element={<ProjectSubNav projectId={7} />}
        />
        <Route
          path="/projects/:id/rules"
          element={<ProjectSubNav projectId={7} />}
        />
        <Route
          path="/projects/:id/api"
          element={<ProjectSubNav projectId={7} />}
        />
        <Route
          path="/projects/:id/review"
          element={<ProjectSubNav projectId={7} />}
        />
        <Route
          path="/projects/:id/schema"
          element={<ProjectSubNav projectId={7} />}
        />
        <Route
          path="/projects/:id/api-console"
          element={<ProjectSubNav projectId={7} />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ProjectSubNav", () => {
  beforeEach(() => {
    localStorage.setItem("emerge.token", "test-token");
    useAuth.setState({
      token: "test-token",
      user: { id: 1, email: "user@example.com", workspace_id: 1 },
      loading: false,
      error: null,
      init: vi.fn().mockResolvedValue(undefined),
    });
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    localStorage.removeItem("emerge.token");
    useAuth.setState({
      token: null,
      user: null,
      loading: false,
      error: null,
      init: originalAuthInit,
    });
  });

  it("renders Documents, Review examples, Extraction rules, and API links", () => {
    renderAt("/projects/7");
    expect(screen.getByRole("link", { name: /^documents$/i })).toHaveAttribute(
      "href",
      "/projects/7",
    );
    expect(
      screen.getByRole("link", { name: /^review examples$/i }),
    ).toHaveAttribute("href", "/projects/7/examples");
    expect(
      screen.getByRole("link", { name: /^extraction rules$/i }),
    ).toHaveAttribute("href", "/projects/7/rules");
    expect(screen.getByRole("link", { name: /^api$/i })).toHaveAttribute(
      "href",
      "/projects/7/api",
    );
  });

  it("marks Review examples current on /projects/:id/examples", () => {
    renderAt("/projects/7/examples");
    expect(
      screen.getByRole("link", { name: /^review examples$/i }),
    ).toHaveAttribute("aria-current", "page");
  });

  it("marks Extraction rules current on /projects/:id/rules", () => {
    renderAt("/projects/7/rules");
    expect(
      screen.getByRole("link", { name: /^extraction rules$/i }),
    ).toHaveAttribute("aria-current", "page");
  });

  it("marks API current on /projects/:id/api", () => {
    renderAt("/projects/7/api");
    expect(
      screen.getByRole("link", { name: /^api$/i }),
    ).toHaveAttribute("aria-current", "page");
  });

  it("marks Review examples current on legacy /projects/:id/review", () => {
    renderAt("/projects/7/review");
    expect(
      screen.getByRole("link", { name: /^review examples$/i }),
    ).toHaveAttribute("aria-current", "page");
  });

  it("marks Extraction rules current on legacy /projects/:id/schema", () => {
    renderAt("/projects/7/schema");
    expect(
      screen.getByRole("link", { name: /^extraction rules$/i }),
    ).toHaveAttribute("aria-current", "page");
  });

  it("marks API current on legacy /projects/:id/api-console", () => {
    renderAt("/projects/7/api-console");
    expect(
      screen.getByRole("link", { name: /^api$/i }),
    ).toHaveAttribute("aria-current", "page");
  });

  it("marks Documents current on /projects/:id", () => {
    renderAt("/projects/7");
    expect(
      screen.getByRole("link", { name: /^documents$/i }),
    ).toHaveAttribute("aria-current", "page");
  });

  it("marks Documents current on /projects/:id/studio/:did", () => {
    renderAt("/projects/7/studio/42");
    expect(
      screen.getByRole("link", { name: /^documents$/i }),
    ).toHaveAttribute("aria-current", "page");
  });

  it.each([
    ["/projects/7/review", "/projects/7/examples", "examples-page"],
    ["/projects/7/schema", "/projects/7/rules", "rules-page"],
    ["/projects/7/api-console", "/projects/7/api", "api-page"],
  ])(
    "redirects legacy route %s to %s",
    async (legacyPath, productPath, pageMarker) => {
      window.history.pushState({}, "", legacyPath);

      await act(async () => {
        render(<App />);
      });

      expect(await screen.findByText(pageMarker)).toBeInTheDocument();
      expect(window.location.pathname).toBe(productPath);
    },
  );
});
