import { create } from "zustand";

import { api, emergeErrorKey } from "@/lib/api";
import { useReadiness } from "@/stores/readiness";
import { useReview } from "@/stores/review";
import type {
  PerFieldConfidence,
  PerFieldEvidence,
} from "@/types/studio";

// Mirror of documents.ts:refreshProjectPanels — saving an Annotation
// shifts the vibe-check pool (in Locked mode it removes the doc; in
// Draft mode the pool stays open but evidence counts change), so the
// readiness + review-queue surfaces need to refetch. Fire-and-forget.
function refreshProjectPanels(projectId: number): void {
  void useReadiness.getState().load(projectId);
  void useReview.getState().load(projectId);
}

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
  // Dogfood follow-up #3: flag-without-correcting. Editing the textbox is
  // the value-correction path; this exists for fields where the issue
  // isn't a value (unparseable output, field doesn't apply). Saves an
  // Annotation with the prediction's output unchanged and the issue_type
  // encoded in `notes` (mirrors public_feedback's `[partial_feedback]=`
  // notes suffix — same concept on the Lab side).
  flagField: (args: {
    projectId: number;
    entityIndex: number;
    fieldName: string;
    issueType: string;
    comment?: string;
  }) => Promise<void>;
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
      refreshProjectPanels(projectId);
    } catch (e) {
      set({ error: emergeErrorKey(e) });
    } finally {
      set({ saving: false });
    }
  },

  async flagField({ projectId, entityIndex, fieldName, issueType, comment }) {
    const { doc } = get();
    if (doc === null) return;
    // Save an Annotation with the prediction's output unchanged so the act
    // of flagging covers the doc in the vibe-check pool the same way
    // editing+saving does. Lab MUST NOT call /extract/{api_code}/feedback —
    // Lab uses session JWT, not X-Api-Key (spec §1; R8.6 hard rules).
    const baseline =
      doc.latest_annotation?.output ?? doc.latest_prediction?.output ?? [];
    set({ saving: true, error: null });
    try {
      const tag = JSON.stringify({
        issue_type: issueType,
        entity_index: entityIndex,
        field_name: fieldName,
        comment: comment ?? null,
      });
      await api.post(
        `/api/v1/projects/${projectId}/documents/${doc.id}/annotations`,
        {
          output: baseline,
          parent_prediction_id: doc.latest_prediction?.id ?? null,
          notes: `[lab_flag]=${tag}`,
        },
      );
      await get().load(projectId, doc.id);
      refreshProjectPanels(projectId);
    } catch (e) {
      set({ error: emergeErrorKey(e) });
    } finally {
      set({ saving: false });
    }
  },
}));
