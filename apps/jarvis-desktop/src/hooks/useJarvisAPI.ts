import type {
  StatusPayload,
  ConfigPayload,
  TasksPayload,
  HermesMCP,
  HermesToolsets,
  HermesMemoryPayload,
  HermesCronJob,
  HermesCronOutput,
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

  // Hermes Control Plane
  getHermesMCPs: () =>
    request<{ mcps: HermesMCP[]; config_path: string; found: boolean }>("/hermes/mcps"),
  saveHermesMCP: (server: {
    name: string;
    command?: string;
    args?: string[];
    url?: string;
    enabled?: boolean;
    env?: Record<string, string>;
  }) =>
    request<{ success: boolean; name?: string; error?: string }>("/hermes/mcps", {
      method: "POST",
      body: JSON.stringify(server),
    }),
  toggleHermesMCP: (name: string) =>
    request<{ success: boolean; enabled?: boolean; error?: string }>(`/hermes/mcps/${name}/toggle`, {
      method: "POST",
    }),
  deleteHermesMCP: (name: string) =>
    request<{ success: boolean; removed?: string; error?: string }>(`/hermes/mcps/${name}`, {
      method: "DELETE",
    }),
  getHermesToolsets: () =>
    request<HermesToolsets>("/hermes/toolsets"),
  getHermesSkills: () =>
    request<{ skills: Array<{ name: string; description: string; source: string; writable: boolean; path: string }> }>("/hermes/skills"),
  getHermesMemory: () => request<HermesMemoryPayload>("/hermes/memory"),
  getHermesCronJobs: () => request<{ jobs: HermesCronJob[]; error?: string }>("/hermes/cron"),
  createHermesCronJob: (prompt: string, schedule: string, name: string) =>
    request<{ success: boolean; job?: HermesCronJob; error?: string }>("/hermes/cron", {
      method: "POST",
      body: JSON.stringify({ prompt, schedule, name }),
    }),
  updateHermesCronJob: (jobId: string, action: "pause" | "resume" | "trigger") =>
    request<{ success: boolean; job?: HermesCronJob; error?: string }>(
      `/hermes/cron/${encodeURIComponent(jobId)}/${action}`,
      { method: "POST" },
    ),
  editHermesCronJob: (jobId: string, updates: { name?: string; prompt?: string; schedule?: string }) =>
    request<{ success: boolean; job?: HermesCronJob; error?: string }>(
      `/hermes/cron/${encodeURIComponent(jobId)}`,
      { method: "PATCH", body: JSON.stringify(updates) },
    ),
  deleteHermesCronJob: (jobId: string) =>
    request<{ success: boolean; removed?: string; error?: string }>(
      `/hermes/cron/${encodeURIComponent(jobId)}`,
      { method: "DELETE" },
    ),
  getHermesCronOutputs: (jobId: string) =>
    request<{ outputs: HermesCronOutput[]; error?: string }>(
      `/hermes/cron/${encodeURIComponent(jobId)}/outputs`,
    ),
  reloadHermesSlow: () =>
    request<{ success: boolean; message?: string; error?: string }>("/hermes/reload-slow", {
      method: "POST",
    }),
  // Hermes Cockpit & Autonomy
  getHermesTasks: () => request<TasksPayload>("/hermes/tasks"),
  dispatchHermesTask: (prompt: string, lane: "slow" | "fast" = "slow") =>
    request<{ call_id: string; status: string; lane: string }>("/hermes/dispatch", {
      method: "POST",
      body: JSON.stringify({ prompt, lane }),
    }),
  getAutonomyStatus: () =>
    request<{ scheduler: any; sentinel: any }>("/hermes/status"),
};
