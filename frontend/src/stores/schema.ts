import { create } from "zustand";

import { api, EmergeError } from "@/lib/api";
import type { SchemaField } from "@/types/schema";

export type ProjectVersion = {
  id: number;
  project_id: number;
  version_number: number;
  schema: SchemaField[];
  global_notes: string;
  model_id: string;
  locked: boolean;
  source: string;
  created_at: string;
};

export type LockStatus = {
  can_lock: boolean;
  reason: string | null;
};

type SchemaState = {
  active: ProjectVersion | null;
  lockStatus: LockStatus | null;
  loading: boolean;
  saving: boolean;
  locking: boolean;
  error: string | null;
  load: (projectId: number) => Promise<void>;
  loadLockStatus: (projectId: number) => Promise<void>;
  save: (
    projectId: number,
    schema: SchemaField[],
    globalNotes: string,
    modelId: string,
  ) => Promise<void>;
  lock: (projectId: number) => Promise<void>;
  unlock: (projectId: number) => Promise<void>;
};

function emergeCode(e: unknown): string {
  return e instanceof EmergeError ? e.code : "INTERNAL_ERROR";
}

export const useSchema = create<SchemaState>((set, get) => ({
  active: null,
  lockStatus: null,
  loading: false,
  saving: false,
  locking: false,
  error: null,

  async load(projectId) {
    set({ loading: true, error: null });
    try {
      const active = (
        await api.get(`/api/v1/projects/${projectId}/versions/active`)
      ).data as ProjectVersion;
      set({ active, loading: false });
    } catch (e) {
      set({ loading: false, error: `errors.${emergeCode(e)}` });
    }
  },

  async loadLockStatus(projectId) {
    try {
      const lockStatus = (
        await api.get(`/api/v1/projects/${projectId}/lock-status`)
      ).data as LockStatus;
      set({ lockStatus });
    } catch (e) {
      set({ error: `errors.${emergeCode(e)}` });
    }
  },

  async save(projectId, schema, globalNotes, modelId) {
    set({ saving: true, error: null });
    try {
      const active = (
        await api.patch(`/api/v1/projects/${projectId}/schema`, {
          schema,
          global_notes: globalNotes,
          model_id: modelId,
        })
      ).data as ProjectVersion;
      set({ active });
      await get().loadLockStatus(projectId);
    } catch (e) {
      set({ error: `errors.${emergeCode(e)}` });
    } finally {
      set({ saving: false });
    }
  },

  async lock(projectId) {
    set({ locking: true, error: null });
    try {
      const active = (await api.post(`/api/v1/projects/${projectId}/lock`)).data as
        | ProjectVersion
        | null;
      if (active) set({ active });
      await get().loadLockStatus(projectId);
    } catch (e) {
      const code = emergeCode(e);
      const reason =
        e instanceof EmergeError ? e.message : null;
      set({
        error: `errors.${code}`,
        lockStatus: reason ? { can_lock: false, reason } : get().lockStatus,
      });
    } finally {
      set({ locking: false });
    }
  },

  async unlock(projectId) {
    set({ locking: true, error: null });
    try {
      const active = (await api.post(`/api/v1/projects/${projectId}/unlock`))
        .data as ProjectVersion;
      set({ active });
      await get().loadLockStatus(projectId);
    } catch (e) {
      set({ error: `errors.${emergeCode(e)}` });
    } finally {
      set({ locking: false });
    }
  },
}));
