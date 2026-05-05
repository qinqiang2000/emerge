import { create } from "zustand";

import { api, emergeErrorKey } from "@/lib/api";
import type { ReviewQueueOut } from "@/types/review";

type ReviewState = {
  data: ReviewQueueOut | null;
  loading: boolean;
  error: string | null;
  load: (projectId: number) => Promise<void>;
};

export const useReview = create<ReviewState>((set) => ({
  data: null,
  loading: false,
  error: null,

  async load(projectId) {
    // Drop the previous project's data before the new request lands so
    // a project switch never flashes stale counts (mirrors useReadiness).
    set({ data: null, loading: true, error: null });
    try {
      const data = (
        await api.get(`/api/v1/projects/${projectId}/review-queue`)
      ).data as ReviewQueueOut;
      set({ data, loading: false });
    } catch (e) {
      set({ loading: false, error: emergeErrorKey(e) });
    }
  },
}));
