import type {
  StatusPayload,
  ConfigPayload,
  TasksPayload,
  HermesMCP,
  HermesToolsets,
  LogEntry,
} from "../types";

const API_BASE = "http://127.0.0.1:8420";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers || {}),
    },
  });
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(errorText || `Error ${res.status} al llamar a ${path}`);
  }
  return res.json() as Promise<T>;
}

export const jarvisAPI = {
  // Config
  getConfig: () => request<ConfigPayload>("/config"),
  updateConfig: (updates: Record<string, string>) =>
    request<{ status: string; updated_keys: string[]; message: string }>("/config", {
      method: "POST",
      body: JSON.stringify({ updates }),
    }),

  // Status & Tasks
  getStatus: () => request<StatusPayload>("/status"),
  getCapabilities: () => request<unknown>("/status/capabilities"),
  getTasks: () => request<TasksPayload>("/status/tasks"),

  // Logs
  getLogs: (n: number = 100) =>
    request<{ logs: LogEntry[]; count: number }>(`/logs?n=${n}`),

  // Actions
  cancelTask: () =>
    request<{ status: string; message: string }>("/actions/cancel-task", {
      method: "POST",
    }),
  toggleMute: () =>
    request<{ status: string; muted: boolean }>("/actions/mute", {
      method: "POST",
    }),
  wake: () =>
    request<{ status: string; state: string }>("/actions/wake", {
      method: "POST",
    }),
  sleep: () =>
    request<{ status: string; state: string }>("/actions/sleep", {
      method: "POST",
    }),
  restartVoice: () =>
    request<{ status: string; message: string }>("/actions/restart-voice", {
      method: "POST",
    }),
  shutdown: () =>
    request<{ status: string; message: string }>("/actions/shutdown", {
      method: "POST",
    }),
  testLive: () =>
    request<{ status: string; live_connected: boolean }>("/actions/test-live", {
      method: "POST",
    }),
  testHermesSlow: () =>
    request<{ status: string; text: string; error?: string }>("/actions/test-hermes-slow", {
      method: "POST",
    }),
  testHermesFast: () =>
    request<{ status: string; text: string; error?: string }>("/actions/test-hermes-fast", {
      method: "POST",
    }),

  // Hermes Info
  getHermesMCPs: () =>
    request<{ mcps: HermesMCP[]; config_path: string; found: boolean }>("/hermes/mcps"),
  getHermesToolsets: () =>
    request<HermesToolsets>("/hermes/toolsets"),
};
