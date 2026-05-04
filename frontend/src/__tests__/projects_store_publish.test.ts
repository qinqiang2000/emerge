import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";
import { useProjects, type Project } from "@/stores/projects";

const PROJECT: Project = {
  id: 1,
  workspace_id: 1,
  name: "JR demo",
  project_type: "extraction",
  template_id: null,
  active_version_id: 7,
  published_version_id: null,
  api_code: null,
  api_published_at: null,
  created_at: "2026-05-04T00:00:00Z",
  created_by: 1,
};

describe("useProjects publish/keys actions", () => {
  beforeEach(() => {
    useProjects.setState({
      rows: [PROJECT],
      apiKeys: [],
      contractDiff: null,
      loading: false,
      error: null,
    });
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

  describe("publish", () => {
    it("POSTs api_code with optional project_version_id and updates rows", async () => {
      const post = vi.spyOn(api, "post").mockResolvedValue({
        data: {
          ...PROJECT,
          api_code: "japan-receipts",
          published_version_id: 7,
          api_published_at: "2026-05-05T00:00:00Z",
        },
      });

      await useProjects.getState().publish(1, "japan-receipts", 7);

      expect(post).toHaveBeenCalledWith("/api/v1/projects/1/publish", {
        api_code: "japan-receipts",
        project_version_id: 7,
      });
      expect(useProjects.getState().rows[0]?.api_code).toBe("japan-receipts");
      expect(useProjects.getState().rows[0]?.published_version_id).toBe(7);
    });

    it("omits project_version_id when not provided", async () => {
      const post = vi.spyOn(api, "post").mockResolvedValue({ data: PROJECT });
      await useProjects.getState().publish(1, "jr");
      expect(post).toHaveBeenCalledWith("/api/v1/projects/1/publish", {
        api_code: "jr",
      });
    });
  });

  describe("unpublish", () => {
    it("POSTs and clears api_published_at on the project row", async () => {
      vi.spyOn(api, "post").mockResolvedValue({
        data: { ...PROJECT, api_code: "jr", api_published_at: null },
      });
      await useProjects.getState().unpublish(1);
      expect(api.post).toHaveBeenCalledWith("/api/v1/projects/1/unpublish");
      expect(useProjects.getState().rows[0]?.api_published_at).toBeNull();
    });
  });

  describe("rollback", () => {
    it("POSTs project_version_id and updates published pointer", async () => {
      vi.spyOn(api, "post").mockResolvedValue({
        data: { ...PROJECT, published_version_id: 5 },
      });
      await useProjects.getState().rollback(1, 5);
      expect(api.post).toHaveBeenCalledWith("/api/v1/projects/1/rollback", {
        project_version_id: 5,
      });
      expect(useProjects.getState().rows[0]?.published_version_id).toBe(5);
    });
  });

  describe("loadContractDiff", () => {
    it("GETs without query when no version ids supplied", async () => {
      const get = vi.spyOn(api, "get").mockResolvedValue({
        data: { has_breaking_changes: false, items: [] },
      });
      await useProjects.getState().loadContractDiff(1);
      expect(get).toHaveBeenCalledWith("/api/v1/projects/1/contract-diff", {
        params: {},
      });
      expect(useProjects.getState().contractDiff).toEqual({
        has_breaking_changes: false,
        items: [],
      });
    });

    it("GETs with explicit from/to version ids", async () => {
      const get = vi.spyOn(api, "get").mockResolvedValue({
        data: {
          from_version_id: 3,
          to_version_id: 5,
          has_breaking_changes: true,
          items: [],
        },
      });
      await useProjects.getState().loadContractDiff(1, 3, 5);
      expect(get).toHaveBeenCalledWith("/api/v1/projects/1/contract-diff", {
        params: { from_version_id: 3, to_version_id: 5 },
      });
    });
  });

  describe("listKeys", () => {
    it("GETs api-keys and stores them", async () => {
      vi.spyOn(api, "get").mockResolvedValue({
        data: [
          {
            id: 9,
            prefix: "ek_abc",
            name: "default",
            last_used_at: null,
            created_at: "2026-05-04T00:00:00Z",
          },
        ],
      });
      await useProjects.getState().listKeys(1);
      expect(api.get).toHaveBeenCalledWith("/api/v1/projects/1/api-keys");
      expect(useProjects.getState().apiKeys).toHaveLength(1);
      expect(useProjects.getState().apiKeys[0]?.prefix).toBe("ek_abc");
    });
  });

  describe("createKey", () => {
    it("POSTs name, returns plaintext to caller exactly once, does NOT persist plaintext", async () => {
      vi.spyOn(api, "post").mockResolvedValue({
        data: {
          id: 9,
          prefix: "ek_abc",
          name: "default",
          key: "ek_abcdefghijklmnopqrstuvwxyz",
        },
      });
      const result = await useProjects.getState().createKey(1, "default");
      expect(api.post).toHaveBeenCalledWith("/api/v1/projects/1/api-keys", {
        name: "default",
      });
      expect(result.key).toBe("ek_abcdefghijklmnopqrstuvwxyz");
      const stateJson = JSON.stringify(useProjects.getState());
      expect(stateJson).not.toContain("ek_abcdefghijklmnopqrstuvwxyz");
    });
  });

  describe("revokeKey", () => {
    it("DELETEs the key and removes the row from apiKeys", async () => {
      useProjects.setState({
        rows: [PROJECT],
        apiKeys: [
          {
            id: 9,
            prefix: "ek_abc",
            name: "default",
            last_used_at: null,
            created_at: "2026-05-04T00:00:00Z",
          },
        ],
        contractDiff: null,
        loading: false,
        error: null,
      });
      vi.spyOn(api, "delete").mockResolvedValue({
        data: {
          id: 9,
          prefix: "ek_abc",
          name: "default",
          last_used_at: null,
          created_at: "2026-05-04T00:00:00Z",
        },
      });
      await useProjects.getState().revokeKey(1, 9);
      expect(api.delete).toHaveBeenCalledWith("/api/v1/projects/1/api-keys/9");
      expect(useProjects.getState().apiKeys).toHaveLength(0);
    });
  });
});
