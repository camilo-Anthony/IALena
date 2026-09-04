import { create } from "zustand";
import type {
  OrbState,
  StatusPayload,
  TasksPayload,
  ConfigPayload,
  LogEntry,
} from "../types";

// ── Constantes ────────────────────────────────────────────
const MAX_LOGS = 300;

// ── State shape ───────────────────────────────────────────
interface JarvisState {
  // Core
  orbState: OrbState;
  status: StatusPayload | null;
  tasks: TasksPayload | null;
  config: ConfigPayload | null;
  logs: LogEntry[];
  wsConnected: boolean;
  activeView: "orb" | "panel" | "hermes";
  activePanelTab: string;

  // Actions
  setOrbState: (s: OrbState) => void;
  setStatus: (s: StatusPayload) => void;
  setTasks: (t: TasksPayload) => void;
  setConfig: (c: ConfigPayload) => void;
  appendLog: (entry: LogEntry) => void;
  prependLogs: (entries: LogEntry[]) => void;
  setWsConnected: (v: boolean) => void;
  setActiveView: (v: "orb" | "panel" | "hermes") => void;
  setActivePanelTab: (t: string) => void;
  clearLogs: () => void;
}

// ── Store ─────────────────────────────────────────────────
export const useJarvisStore = create<JarvisState>((set) => ({
  orbState: "dormant",
  status: null,
  tasks: null,
  config: null,
  logs: [],
  wsConnected: false,
  activeView: "orb",
  activePanelTab: "dashboard",

  setOrbState: (orbState) => set({ orbState }),

  setStatus: (status) =>
    set((s) => ({
      status,
      orbState: status.orb_state ?? s.orbState,
    })),

  setTasks: (tasks) => set({ tasks }),

  setConfig: (config) => set({ config }),

  appendLog: (entry) =>
    set((s) => ({
      logs: [entry, ...s.logs].slice(0, MAX_LOGS),
    })),

  prependLogs: (entries) =>
    set((s) => ({
      logs: [...entries.reverse(), ...s.logs].slice(0, MAX_LOGS),
    })),

  setWsConnected: (wsConnected) => set({ wsConnected }),

  setActiveView: (activeView) => set({ activeView }),

  setActivePanelTab: (activePanelTab) => set({ activePanelTab }),

  clearLogs: () => set({ logs: [] }),
}));
