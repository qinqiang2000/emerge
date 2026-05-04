import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";

import { ProjectListPage } from "@/pages/ProjectList";
import { useProjects, type Project } from "@/stores/projects";

const PUBLISHED: Project = {
  id: 1,
  workspace_id: 1,
  name: "Japan receipts",
  project_type: "extraction",
  template_id: null,
  active_version_id: 7,
  published_version_id: 7,
  api_code: "japan-receipts",
  api_published_at: "2026-05-04T10:00:00Z",
  created_at: "2026-05-01T00:00:00Z",
  created_by: 1,
};

const DRAFT: Project = {
  id: 2,
  workspace_id: 1,
  name: "China VAT",
  project_type: "extraction",
  template_id: null,
  active_version_id: 1,
  published_version_id: null,
  api_code: null,
  api_published_at: null,
  created_at: "2026-05-02T00:00:00Z",
  created_by: 1,
};

function renderList() {
  return render(
    <MemoryRouter>
      <ProjectListPage />
    </MemoryRouter>,
  );
}

describe("ProjectListPage published/draft badge", () => {
  beforeEach(() => {
    useProjects.setState({
      rows: [PUBLISHED, DRAFT],
      loading: false,
      error: null,
    });
  });

  it("renders one Published badge and one Draft badge", () => {
    renderList();
    expect(screen.getAllByText("Published")).toHaveLength(1);
    expect(screen.getAllByText("Draft")).toHaveLength(1);
  });

  it("attaches the Published badge to the published row only", () => {
    renderList();
    const publishedRow = screen.getByText("Japan receipts").closest("tr");
    const draftRow = screen.getByText("China VAT").closest("tr");
    expect(publishedRow).not.toBeNull();
    expect(draftRow).not.toBeNull();
    expect(within(publishedRow!).getByText("Published")).toBeInTheDocument();
    expect(within(draftRow!).getByText("Draft")).toBeInTheDocument();
  });

  it("treats projects with api_published_at but no published_version_id as Draft", () => {
    useProjects.setState({
      rows: [
        { ...PUBLISHED, published_version_id: null },
      ],
      loading: false,
      error: null,
    });
    renderList();
    expect(screen.queryByText("Published")).not.toBeInTheDocument();
    expect(screen.getByText("Draft")).toBeInTheDocument();
  });
});
