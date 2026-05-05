import { create } from "zustand";

import { api, emergeErrorKey } from "@/lib/api";
import type {
  PerFieldConfidence,
  PerFieldEvidence,
} from "@/types/studio";

export type EntityOutput = Record<string, unknown>;

export type LatestPrediction = {
  id: number;
  output: EntityOutput[];
  status: string;
  model_id: string;
  tokens_used: number | null;
  error_message: string | null;
  per_field_confidence?: PerFieldConfidence | null;
  per_field_evidence?: PerFieldEvidence | null;
};

export type LatestAnnotation = {
  id: number;
  output: EntityOutput[];
  role: string;
  notes: string | null;
};

export type DocumentDetail = {
  id: number;
  project_id: number;
  filename: string;
  mime_type: string;
  page_count: number;
  byte_size: number;
  status: string;
  created_at: string;
  latest_prediction: LatestPrediction | null;
  latest_annotation: LatestAnnotation | null;
};

type StudioState = {
  doc: DocumentDetail | null;
  draft: EntityOutput[];
  loading: boolean;
  saving: boolean;
  error: string | null;
  load: (projectId: number, documentId: number) => Promise<void>;
  setDraft: (next: EntityOutput[]) => void;
  save: (projectId: number) => Promise<void>;
};

function seedDraft(doc: DocumentDetail): EntityOutput[] {
  if (doc.latest_annotation?.output) return doc.latest_annotation.output;
  if (doc.latest_prediction?.output) return doc.latest_prediction.output;
  return [];
}

export const useStudio = create<StudioState>((set, get) => ({
  doc: null,
  draft: [],
  loading: false,
  saving: false,
  error: null,

  async load(projectId, documentId) {
    set({ loading: true, error: null });
    try {
      const doc = (
        await api.get(`/api/v1/projects/${projectId}/documents/${documentId}`)
      ).data as DocumentDetail;
      set({ doc, draft: seedDraft(doc), loading: false });
    } catch (e) {
      set({ loading: false, error: emergeErrorKey(e) });
    }
  },

  setDraft(next) {
    set({ draft: next });
  },

  async save(projectId) {
    const { doc, draft } = get();
    if (doc === null) return;
    set({ saving: true, error: null });
    try {
      await api.post(
        `/api/v1/projects/${projectId}/documents/${doc.id}/annotations`,
        {
          output: draft,
          parent_prediction_id: doc.latest_prediction?.id ?? null,
        },
      );
      await get().load(projectId, doc.id);
    } catch (e) {
      set({ error: emergeErrorKey(e) });
    } finally {
      set({ saving: false });
    }
  },
}));
