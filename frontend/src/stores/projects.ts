import { create } from "zustand";

import { api, EmergeError } from "@/lib/api";

export type Project = {
  id: number;
  workspace_id: number;
  name: string;
  project_type: string;
  template_id: number | null;
  active_version_id: number | null;
  published_version_id: number | null;
  api_code: string | null;
  api_published_at: string | null;
  created_at: string;
  created_by: number;
};

export type ApiKeyOut = {
  id: number;
  prefix: string;
  name: string;
  last_used_at: string | null;
  created_at: string;
};

export type ApiKeyOnce = {
  id: number;
  prefix: string;
  name: string;
  key: string;
};

export type ContractDiffItem = {
  kind: string;
  severity: "breaking" | "non_breaking";
  field_name: string | null;
  before: unknown;
  after: unknown;
  message: string;
};

export type ContractDiff = {
  from_version_id?: number | null;
  to_version_id?: number | null;
  has_breaking_changes: boolean;
  items: ContractDiffItem[];
};

type ProjectsState = {
  rows: Project[];
  apiKeys: ApiKeyOut[];
  contractDiff: ContractDiff | null;
  loading: boolean;
  error: string | null;
  load: () => Promise<void>;
  publish: (
    projectId: number,
    apiCode: string,
    projectVersionId?: number,
  ) => Promise<void>;
  unpublish: (projectId: number) => Promise<void>;
  rollback: (projectId: number, projectVersionId: number) => Promise<void>;
  loadContractDiff: (
    projectId: number,
    fromVersionId?: number,
    toVersionId?: number,
  ) => Promise<void>;
  listKeys: (projectId: number) => Promise<void>;
  createKey: (projectId: number, name: string) => Promise<ApiKeyOnce>;
  revokeKey: (projectId: number, keyId: number) => Promise<void>;
};

function emergeCode(e: unknown): string {
  return e instanceof EmergeError ? e.code : "INTERNAL_ERROR";
}

function spliceProject(rows: Project[], updated: Project): Project[] {
  const i = rows.findIndex((p) => p.id === updated.id);
  if (i < 0) return [...rows, updated];
  const next = rows.slice();
  next[i] = updated;
  return next;
}

export const useProjects = create<ProjectsState>((set, get) => ({
  rows: [],
  apiKeys: [],
  contractDiff: null,
  loading: false,
  error: null,

  async load() {
    set({ loading: true, error: null });
    try {
      const rows = (await api.get("/api/v1/projects")).data as Project[];
      set({ rows, loading: false });
    } catch (e) {
      set({ loading: false, error: `errors.${emergeCode(e)}` });
    }
  },

  async publish(projectId, apiCode, projectVersionId) {
    set({ error: null });
    try {
      const body: { api_code: string; project_version_id?: number } = {
        api_code: apiCode,
      };
      if (projectVersionId !== undefined) body.project_version_id = projectVersionId;
      const updated = (await api.post(`/api/v1/projects/${projectId}/publish`, body))
        .data as Project;
      set({ rows: spliceProject(get().rows, updated) });
    } catch (e) {
      set({ error: `errors.${emergeCode(e)}` });
      throw e;
    }
  },

  async unpublish(projectId) {
    set({ error: null });
    try {
      const updated = (
        await api.post(`/api/v1/projects/${projectId}/unpublish`)
      ).data as Project;
      set({ rows: spliceProject(get().rows, updated) });
    } catch (e) {
      set({ error: `errors.${emergeCode(e)}` });
      throw e;
    }
  },

  async rollback(projectId, projectVersionId) {
    set({ error: null });
    try {
      const updated = (
        await api.post(`/api/v1/projects/${projectId}/rollback`, {
          project_version_id: projectVersionId,
        })
      ).data as Project;
      set({ rows: spliceProject(get().rows, updated) });
    } catch (e) {
      set({ error: `errors.${emergeCode(e)}` });
      throw e;
    }
  },

  async loadContractDiff(projectId, fromVersionId, toVersionId) {
    set({ error: null });
    try {
      const params: Record<string, number> = {};
      if (fromVersionId !== undefined) params.from_version_id = fromVersionId;
      if (toVersionId !== undefined) params.to_version_id = toVersionId;
      const diff = (
        await api.get(`/api/v1/projects/${projectId}/contract-diff`, {
          params,
        })
      ).data as ContractDiff;
      set({ contractDiff: diff });
    } catch (e) {
      set({ error: `errors.${emergeCode(e)}` });
    }
  },

  async listKeys(projectId) {
    set({ error: null });
    try {
      const apiKeys = (
        await api.get(`/api/v1/projects/${projectId}/api-keys`)
      ).data as ApiKeyOut[];
      set({ apiKeys });
    } catch (e) {
      set({ error: `errors.${emergeCode(e)}` });
    }
  },

  async createKey(projectId, name) {
    const once = (
      await api.post(`/api/v1/projects/${projectId}/api-keys`, { name })
    ).data as ApiKeyOnce;
    // Append a redacted ApiKeyOut to the visible list — never persist plaintext.
    const visible: ApiKeyOut = {
      id: once.id,
      prefix: once.prefix,
      name: once.name,
      last_used_at: null,
      created_at: new Date().toISOString(),
    };
    set({ apiKeys: [visible, ...get().apiKeys] });
    return once;
  },

  async revokeKey(projectId, keyId) {
    set({ error: null });
    try {
      await api.delete(`/api/v1/projects/${projectId}/api-keys/${keyId}`);
      set({ apiKeys: get().apiKeys.filter((k) => k.id !== keyId) });
    } catch (e) {
      set({ error: `errors.${emergeCode(e)}` });
      throw e;
    }
  },
}));

export function isProjectPublished(p: Project): boolean {
  return p.api_published_at !== null && p.published_version_id !== null;
}
