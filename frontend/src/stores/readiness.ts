import { create } from "zustand";

import { api, emergeErrorKey } from "@/lib/api";
import type { APIReadinessOut } from "@/types/readiness";

type ReadinessState = {
  data: APIReadinessOut | null;
  loading: boolean;
  error: string | null;
  load: (projectId: number) => Promise<void>;
};

export const useReadiness = create<ReadinessState>((set) => ({
  data: null,
  loading: false,
  error: null,

  async load(projectId) {
    set({ loading: true, error: null });
    try {
      const data = (
        await api.get(`/api/v1/projects/${projectId}/readiness`)
      ).data as APIReadinessOut;
      set({ data, loading: false });
    } catch (e) {
      set({ loading: false, error: emergeErrorKey(e) });
    }
  },
}));
