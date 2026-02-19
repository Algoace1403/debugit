import { create } from "zustand";
import type { GitHubUser, Results, RunStatus, WSEvent } from "../types";

interface HealState {
  // Auth
  user: GitHubUser | null;
  setUser: (u: GitHubUser | null) => void;
  logout: () => void;

  // Form
  repoUrl: string;
  teamName: string;
  leaderName: string;
  setRepoUrl: (v: string) => void;
  setTeamName: (v: string) => void;
  setLeaderName: (v: string) => void;

  // Run
  runId: string | null;
  runStatus: RunStatus | null;
  results: Results | null;
  wsEvents: WSEvent[];
  loading: boolean;
  error: string | null;

  // Actions
  startRun: (runId: string) => void;
  setRunStatus: (s: RunStatus) => void;
  setResults: (r: Results) => void;
  addWsEvent: (e: WSEvent) => void;
  setLoading: (v: boolean) => void;
  setError: (v: string | null) => void;
  reset: () => void;
}

// Load persisted user from localStorage
function loadUser(): GitHubUser | null {
  try {
    const raw = localStorage.getItem("github_user");
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export const useHealStore = create<HealState>((set) => ({
  // Auth
  user: loadUser(),
  setUser: (u) => {
    if (u) {
      localStorage.setItem("github_user", JSON.stringify(u));
    } else {
      localStorage.removeItem("github_user");
    }
    set({ user: u });
  },
  logout: () => {
    localStorage.removeItem("github_user");
    set({ user: null });
  },

  // Form defaults
  repoUrl: "",
  teamName: "",
  leaderName: "",
  setRepoUrl: (v) => set({ repoUrl: v }),
  setTeamName: (v) => set({ teamName: v }),
  setLeaderName: (v) => set({ leaderName: v }),

  // Run defaults
  runId: null,
  runStatus: null,
  results: null,
  wsEvents: [],
  loading: false,
  error: null,

  startRun: (runId) =>
    set({ runId, runStatus: null, results: null, wsEvents: [], error: null }),
  setRunStatus: (s) => set({ runStatus: s }),
  setResults: (r) => set({ results: r, loading: false }),
  addWsEvent: (e) =>
    set((state) => ({ wsEvents: [...state.wsEvents, e] })),
  setLoading: (v) => set({ loading: v }),
  setError: (v) => set({ error: v, loading: false }),
  reset: () =>
    set({
      runId: null,
      runStatus: null,
      results: null,
      wsEvents: [],
      loading: false,
      error: null,
    }),
}));
