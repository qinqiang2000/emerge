import { create } from "zustand";

import { api, EmergeError, setAuthToken } from "@/lib/api";

type User = { id: number; email: string; workspace_id: number };

type AuthState = {
  token: string | null;
  user: User | null;
  loading: boolean;
  error: string | null;
  init: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
};

export const useAuth = create<AuthState>((set) => ({
  token: localStorage.getItem("emerge.token"),
  user: null,
  loading: false,
  error: null,

  async init() {
    const token = localStorage.getItem("emerge.token");
    if (!token) return;
    setAuthToken(token);
    try {
      const me = (await api.get("/api/v1/me")).data;
      set({ user: me, token });
    } catch {
      localStorage.removeItem("emerge.token");
      setAuthToken(null);
      set({ token: null, user: null });
    }
  },

  async login(email, password) {
    set({ loading: true, error: null });
    try {
      const tok = (await api.post("/api/v1/auth/login", { email, password })).data
        .access_token as string;
      localStorage.setItem("emerge.token", tok);
      setAuthToken(tok);
      const me = (await api.get("/api/v1/me")).data;
      set({ token: tok, user: me, loading: false });
    } catch (e) {
      const msg = e instanceof EmergeError ? `errors.${e.code}` : "errors.INTERNAL_ERROR";
      set({ loading: false, error: msg });
    }
  },

  async register(email, password) {
    set({ loading: true, error: null });
    try {
      await api.post("/api/v1/auth/register", { email, password });
      await useAuth.getState().login(email, password);
    } catch (e) {
      const msg = e instanceof EmergeError ? `errors.${e.code}` : "errors.INTERNAL_ERROR";
      set({ loading: false, error: msg });
    }
  },

  logout() {
    localStorage.removeItem("emerge.token");
    setAuthToken(null);
    set({ token: null, user: null });
  },
}));
