import { create } from "zustand";

import { api, EmergeError } from "@/lib/api";

export type DocumentRow = {
  id: number;
  project_id: number;
  filename: string;
  mime_type: string;
  page_count: number;
  byte_size: number;
  status: string;
  created_at: string;
};

type DocumentsState = {
  rows: DocumentRow[];
  loading: boolean;
  extracting: boolean;
  uploading: boolean;
  error: string | null;
  load: (projectId: number) => Promise<void>;
  upload: (projectId: number, files: File[]) => Promise<void>;
  triggerExtract: (projectId: number) => Promise<void>;
};

export const useDocuments = create<DocumentsState>((set, get) => ({
  rows: [],
  loading: false,
  extracting: false,
  uploading: false,
  error: null,

  async load(projectId) {
    set({ loading: true, error: null });
    try {
      const rows = (await api.get(`/api/v1/projects/${projectId}/documents`))
        .data as DocumentRow[];
      set({ rows, loading: false });
    } catch (e) {
      const code = e instanceof EmergeError ? e.code : "INTERNAL_ERROR";
      set({ loading: false, error: `errors.${code}` });
    }
  },

  async upload(projectId, files) {
    if (files.length === 0) return;
    set({ uploading: true, error: null });
    try {
      const fd = new FormData();
      for (const f of files) fd.append("files", f);
      await api.post(`/api/v1/projects/${projectId}/documents`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      await get().load(projectId);
    } catch (e) {
      const code = e instanceof EmergeError ? e.code : "INTERNAL_ERROR";
      set({ error: `errors.${code}` });
    } finally {
      set({ uploading: false });
    }
  },

  async triggerExtract(projectId) {
    set({ extracting: true, error: null });
    try {
      await api.post(`/api/v1/projects/${projectId}/extract`);
      await get().load(projectId);
    } catch (e) {
      const code = e instanceof EmergeError ? e.code : "INTERNAL_ERROR";
      set({ error: `errors.${code}` });
    } finally {
      set({ extracting: false });
    }
  },
}));
