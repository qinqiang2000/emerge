import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";
import { SchemaEditorPage } from "@/pages/SchemaEditor";
import { useSchema, type ProjectVersion } from "@/stores/schema";

const ACTIVE_VERSION: ProjectVersion = {
  id: 7,
  project_id: 7,
  version_number: 1,
  schema: [
    {
      name: "total",
      type: "string",
      required: true,
      description: "Tax-included receipt total in JPY",
      examples: [],
      enum: null,
      child_fields: [],
    },
  ],
  global_notes: "",
  model_id: "gemini-2.5-flash",
  locked: false,
  source: "user_edit",
  created_at: "2026-05-04T00:00:00Z",
};

function renderEditor() {
  return render(
    <MemoryRouter initialEntries={["/projects/7/schema"]}>
      <Routes>
        <Route path="/projects/:id/schema" element={<SchemaEditorPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

async function settle() {
  await waitFor(() => {
    const s = useSchema.getState();
    expect(s.loading).toBe(false);
    expect(s.saving).toBe(false);
    expect(s.locking).toBe(false);
  });
}

describe("SchemaEditorPage form mode", () => {
  beforeEach(() => {
    useSchema.setState({
      active: ACTIVE_VERSION,
      lockStatus: { can_lock: true, reason: null },
      loading: false,
      saving: false,
      locking: false,
      error: null,
    });
    vi.spyOn(api, "get").mockImplementation((url: string) => {
      if (url.endsWith("/lock-status"))
        return Promise.resolve({ data: { can_lock: true, reason: null } });
      return Promise.resolve({ data: ACTIVE_VERSION });
    });
  });
  afterEach(() => {
    vi.restoreAllMocks();
    useSchema.setState({
      active: null,
      lockStatus: null,
      loading: false,
      saving: false,
      locking: false,
      error: null,
    });
  });

  it("renders one field with editable description and shows Lock button when unlocked", async () => {
    renderEditor();
    await settle();
    expect(
      screen.getByDisplayValue("Tax-included receipt total in JPY"),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^lock schema$/i })).toBeInTheDocument();
  });

  it("Save calls PATCH /schema with full schema/notes/model_id payload", async () => {
    const post = vi.spyOn(api, "post").mockResolvedValue({ data: {} });
    const patch = vi
      .spyOn(api, "patch")
      .mockResolvedValue({ data: { ...ACTIVE_VERSION, version_number: 2 } });

    renderEditor();
    await settle();

    fireEvent.change(
      screen.getByDisplayValue("Tax-included receipt total in JPY"),
      { target: { value: "Tax-included total, JPY only" } },
    );
    fireEvent.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => expect(patch).toHaveBeenCalledTimes(1));
    expect(patch).toHaveBeenCalledWith("/api/v1/projects/7/schema", {
      schema: [
        {
          name: "total",
          type: "string",
          required: true,
          description: "Tax-included total, JPY only",
          examples: [],
          enum: null,
          child_fields: [],
        },
      ],
      global_notes: "",
      model_id: "gemini-2.5-flash",
    });
    expect(post).not.toHaveBeenCalled();
    await settle();
  });

  it("surfaces lock-status reason when can_lock is false and disables Lock button", async () => {
    useSchema.setState({
      active: ACTIVE_VERSION,
      lockStatus: { can_lock: false, reason: "Need at least 2 saved corrections." },
      loading: false,
      saving: false,
      locking: false,
      error: null,
    });
    vi.spyOn(api, "get").mockImplementation((url: string) => {
      if (url.endsWith("/lock-status"))
        return Promise.resolve({
          data: {
            can_lock: false,
            reason: "Need at least 2 saved corrections.",
          },
        });
      return Promise.resolve({ data: ACTIVE_VERSION });
    });

    renderEditor();
    await settle();

    expect(
      screen.getByText("Need at least 2 saved corrections."),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /^lock schema$/i }),
    ).toBeDisabled();
  });

  it("when version is locked, Lock button flips to Unlock", async () => {
    useSchema.setState({
      active: { ...ACTIVE_VERSION, locked: true },
      lockStatus: { can_lock: true, reason: null },
      loading: false,
      saving: false,
      locking: false,
      error: null,
    });
    vi.spyOn(api, "get").mockImplementation((url: string) => {
      if (url.endsWith("/lock-status"))
        return Promise.resolve({ data: { can_lock: true, reason: null } });
      return Promise.resolve({
        data: { ...ACTIVE_VERSION, locked: true },
      });
    });

    renderEditor();
    await settle();
    expect(
      screen.getByRole("button", { name: /^unlock$/i }),
    ).toBeInTheDocument();
  });
});
