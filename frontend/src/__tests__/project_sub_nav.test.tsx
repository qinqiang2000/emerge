import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { ProjectSubNav } from "@/components/ProjectSubNav";

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
          path="/projects/:id/schema"
          element={<ProjectSubNav projectId={7} />}
        />
        <Route
          path="/projects/:id/api-console"
          element={<ProjectSubNav projectId={7} />}
        />
        <Route
          path="/projects/:id/review"
          element={<ProjectSubNav projectId={7} />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ProjectSubNav", () => {
  it("renders Documents, Review, Schema, and API links pointing to project routes", () => {
    renderAt("/projects/7");
    expect(screen.getByRole("link", { name: /documents/i })).toHaveAttribute(
      "href",
      "/projects/7",
    );
    expect(screen.getByRole("link", { name: /review/i })).toHaveAttribute(
      "href",
      "/projects/7/review",
    );
    expect(screen.getByRole("link", { name: /schema/i })).toHaveAttribute(
      "href",
      "/projects/7/schema",
    );
    expect(screen.getByRole("link", { name: /^api$/i })).toHaveAttribute(
      "href",
      "/projects/7/api-console",
    );
  });

  it("marks Review as current when on /projects/:id/review", () => {
    renderAt("/projects/7/review");
    expect(
      screen.getByRole("link", { name: /review/i }),
    ).toHaveAttribute("aria-current", "page");
    expect(
      screen.getByRole("link", { name: /documents/i }),
    ).not.toHaveAttribute("aria-current");
  });

  it("marks API as current when on /projects/:id/api-console", () => {
    renderAt("/projects/7/api-console");
    expect(
      screen.getByRole("link", { name: /^api$/i }),
    ).toHaveAttribute("aria-current", "page");
    expect(
      screen.getByRole("link", { name: /documents/i }),
    ).not.toHaveAttribute("aria-current");
    expect(
      screen.getByRole("link", { name: /schema/i }),
    ).not.toHaveAttribute("aria-current");
  });

  it("marks Documents as current when on /projects/:id", () => {
    renderAt("/projects/7");
    expect(
      screen.getByRole("link", { name: /documents/i }),
    ).toHaveAttribute("aria-current", "page");
    expect(
      screen.getByRole("link", { name: /schema/i }),
    ).not.toHaveAttribute("aria-current");
  });

  it("marks Documents as current when on /projects/:id/studio/:did", () => {
    renderAt("/projects/7/studio/42");
    expect(
      screen.getByRole("link", { name: /documents/i }),
    ).toHaveAttribute("aria-current", "page");
  });

  it("marks Schema as current when on /projects/:id/schema", () => {
    renderAt("/projects/7/schema");
    expect(
      screen.getByRole("link", { name: /schema/i }),
    ).toHaveAttribute("aria-current", "page");
    expect(
      screen.getByRole("link", { name: /documents/i }),
    ).not.toHaveAttribute("aria-current");
  });
});
