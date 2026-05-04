import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";
import { ProjectCreatePage } from "@/pages/ProjectCreate";
import { useTemplates, type Template } from "@/stores/templates";

const JAPAN_RECEIPT: Template = {
  id: 11,
  workspace_id: null,
  name: "japan_receipt",
  description: "Japanese tax-inclusive receipts",
  version: 1,
  schema: [],
  global_notes: "",
  recommended_model_id: "gemini-2.5-flash",
  builtin: true,
  created_at: "2026-04-01T00:00:00Z",
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/projects/new"]}>
      <Routes>
        <Route path="/projects/new" element={<ProjectCreatePage />} />
        <Route path="/projects/:id" element={<div>routed</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ProjectCreatePage", () => {
  beforeEach(() => {
    useTemplates.setState({ rows: [JAPAN_RECEIPT], loading: false, error: null });
    vi.spyOn(api, "get").mockResolvedValue({ data: [JAPAN_RECEIPT] });
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders builtin template name and Empty project button", async () => {
    renderPage();
    expect(await screen.findByText("japan_receipt")).toBeInTheDocument();
    expect(screen.getByText("Empty project")).toBeInTheDocument();
  });

  it("posts {name, template_id} when a builtin is chosen", async () => {
    const post = vi
      .spyOn(api, "post")
      .mockResolvedValue({ data: { id: 42 } });

    renderPage();
    fireEvent.change(await screen.findByLabelText(/project name/i), {
      target: { value: "JR demo" },
    });
    fireEvent.click(screen.getByText("japan_receipt"));

    await waitFor(() => expect(post).toHaveBeenCalledTimes(1));
    expect(post).toHaveBeenCalledWith("/api/v1/projects", {
      name: "JR demo",
      template_id: 11,
    });
    await screen.findByText("routed");
  });

  it("posts {name, template_id: null} for Empty project", async () => {
    const post = vi
      .spyOn(api, "post")
      .mockResolvedValue({ data: { id: 43 } });

    renderPage();
    fireEvent.change(await screen.findByLabelText(/project name/i), {
      target: { value: "Blank" },
    });
    fireEvent.click(screen.getByText("Empty project"));

    await waitFor(() => expect(post).toHaveBeenCalledTimes(1));
    expect(post).toHaveBeenCalledWith("/api/v1/projects", {
      name: "Blank",
      template_id: null,
    });
    await screen.findByText("routed");
  });

  it("does not submit if name is empty", async () => {
    const post = vi.spyOn(api, "post").mockResolvedValue({ data: { id: 0 } });
    renderPage();
    fireEvent.click(await screen.findByText("japan_receipt"));
    expect(post).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText("Empty project"));
    expect(post).not.toHaveBeenCalled();
  });
});
