import { create } from "zustand";

import { api, emergeErrorKey } from "@/lib/api";
import { useReadiness } from "@/stores/readiness";
import { useReview } from "@/stores/review";

// After a document mutation, ReadinessPanel + ReviewInboxBanner state
// becomes stale (vibe-check pool changes, evidence counts shift). The
// stores don't subscribe to each other, so we explicitly invalidate
// them here. Surfaced by R8.7 smoke as "panels show 0 docs after I
// just uploaded one — until I reload the page". Fire-and-forget so a
// transient panel-fetch failure doesn't block the document mutation
// path itself.
function refreshProjectPanels(projectId: number): void {
  void useReadiness.getState().load(projectId);
  void useReview.getState().load(projectId);
}

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
      set({ loading: false, error: emergeErrorKey(e) });
    }
  },

  async upload(projectId, files) {
    if (files.length === 0) return;
    set({ uploading: true, error: null });
    try {
      const fd = new FormData();
      for (const f of files) fd.append("files", f);
      // Axios sets Content-Type with the correct multipart boundary when given
      // a FormData body. Setting it manually drops the boundary suffix.
      await api.post(`/api/v1/projects/${projectId}/documents`, fd);
      await get().load(projectId);
      refreshProjectPanels(projectId);
    } catch (e) {
      set({ error: emergeErrorKey(e) });
    } finally {
      set({ uploading: false });
    }
  },

  async triggerExtract(projectId) {
    set({ extracting: true, error: null });
    try {
      await api.post(`/api/v1/projects/${projectId}/extract`);
      await get().load(projectId);
      refreshProjectPanels(projectId);
    } catch (e) {
      set({ error: emergeErrorKey(e) });
    } finally {
      set({ extracting: false });
    }
  },
}));
