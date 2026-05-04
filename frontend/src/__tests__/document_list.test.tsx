import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";
import { DocumentListPage } from "@/pages/DocumentList";
import { useDocuments, type DocumentRow } from "@/stores/documents";

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
    vi.spyOn(api, "get").mockResolvedValue({
      data: [UPLOADED, EXTRACTED],
    });
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
  });

  it("renders filename and status for each row", async () => {
    renderPage();
    await settle();
    expect(screen.getByText("receipt-001.pdf")).toBeInTheDocument();
    expect(screen.getByText("receipt-002.pdf")).toBeInTheDocument();
    expect(screen.getByText("uploaded")).toBeInTheDocument();
    expect(screen.getByText("extracted")).toBeInTheDocument();
  });

  it("clicking a row navigates to /projects/:id/studio/:did", async () => {
    renderPage();
    await settle();
    fireEvent.click(screen.getByText("receipt-001.pdf"));
    expect(await screen.findByText("studio-routed")).toBeInTheDocument();
  });

  it("upload triggers POST with multipart FormData and re-fetches list", async () => {
    const post = vi.spyOn(api, "post").mockResolvedValue({ data: [UPLOADED] });
    const get = vi
      .spyOn(api, "get")
      .mockResolvedValue({ data: [UPLOADED, EXTRACTED] });

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
      expect.objectContaining({
        headers: expect.objectContaining({
          "Content-Type": "multipart/form-data",
        }),
      }),
    );
    const fd = post.mock.calls[0]![1] as FormData;
    expect(fd.getAll("files")).toHaveLength(1);
    await waitFor(() => expect(get).toHaveBeenCalled());
    await settle();
  });

  it("extract button POSTs and re-fetches list afterwards", async () => {
    const post = vi.spyOn(api, "post").mockResolvedValue({ data: "ok" });
    const get = vi
      .spyOn(api, "get")
      .mockResolvedValue({ data: [UPLOADED, EXTRACTED] });

    renderPage();
    await settle();
    fireEvent.click(screen.getByRole("button", { name: /re-extract/i }));

    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post).toHaveBeenCalledWith("/api/v1/projects/7/extract");
    await waitFor(() => expect(get).toHaveBeenCalled());
    await settle();
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
    vi.spyOn(api, "get").mockResolvedValue({ data: [] });
    renderPage();
    await settle();
    expect(screen.getByText(/no documents/i)).toBeInTheDocument();
  });
});
