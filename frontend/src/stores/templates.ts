import { create } from "zustand";

import { api, EmergeError } from "@/lib/api";
import type { SchemaField } from "@/types/schema";

export type Template = {
  id: number;
  workspace_id: number | null;
  name: string;
  description: string;
  version: number;
  schema: SchemaField[];
  global_notes: string;
  recommended_model_id: string;
  builtin: boolean;
  created_at: string;
};

type TemplatesState = {
  rows: Template[];
  loading: boolean;
  error: string | null;
  load: () => Promise<void>;
};

export const useTemplates = create<TemplatesState>((set) => ({
  rows: [],
  loading: false,
  error: null,
  async load() {
    set({ loading: true, error: null });
    try {
      const rows = (await api.get("/api/v1/templates")).data as Template[];
      set({ rows, loading: false });
    } catch (e) {
      const code = e instanceof EmergeError ? e.code : "INTERNAL_ERROR";
      set({ loading: false, error: `errors.${code}` });
    }
  },
}));
