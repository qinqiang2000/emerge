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

type ProjectsState = {
  rows: Project[];
  loading: boolean;
  error: string | null;
  load: () => Promise<void>;
};

export const useProjects = create<ProjectsState>((set) => ({
  rows: [],
  loading: false,
  error: null,
  async load() {
    set({ loading: true, error: null });
    try {
      const rows = (await api.get("/api/v1/projects")).data as Project[];
      set({ rows, loading: false });
    } catch (e) {
      const code = e instanceof EmergeError ? e.code : "INTERNAL_ERROR";
      set({ loading: false, error: `errors.${code}` });
    }
  },
}));

export function isProjectPublished(p: Project): boolean {
  return p.api_published_at !== null && p.published_version_id !== null;
}
