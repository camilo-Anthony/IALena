// ── JARVIS Desktop — Tipos compartidos ──────────────────────────────────────

export type OrbState =
  | "dormant"
  | "listening"
  | "speaking"
  | "thinking_fast"
  | "working_slow"
  | "delivery_waiting"
  | "reconnecting"
  | "confirmation_pending"
  | "error";

export interface TaskItem {
  task_id: string;
  lane: string;
  prompt: string;
  state: string;
  result?: string;
  error?: string;
  created_at?: number;
  completed_at?: number;
  duration?: number;
}

export interface TasksPayload {
  running_slow: TaskItem[];
  running_fast: TaskItem[];
  pending_slow: TaskItem[];
  recent: TaskItem[];
}

export interface KeyRotatorStatus {
  pool_size: number;
  call_count: number;
  active_key_masked: string;
}

export interface DeliveryQueueStatus {
  pending: number;
  delivering: number;
}

export interface TaskStatusPayload {
  status: "idle" | "running" | "queued" | "pending_confirmation";
  active: boolean;
  pending: number;
  running_slow_count: number;
  running_fast_count: number;
  message: string;
}

export interface CapabilitiesSnapshot {
  slow_toolsets: string[];
  slow_tools: string[];
  fast_toolsets: string[];
  fast_tools: string[];
  timestamp: number;
}

export interface WakeWordDetectorMetrics {
  ready?: boolean;
  models?: string[];
  threshold?: number;
  consecutive_frames_required?: number;
  cooldown_seconds?: number;
  total_detections?: number;
  total_inferences?: number;
  avg_inference_ms?: number;
  avg_score?: number;
  last_detected_model?: string;
  last_detected_score?: number;
  last_detected_at?: number;
}

export interface WakeWordStatus {
  pipeline_running?: boolean;
  wake_word_enabled?: boolean;
  pre_roll_ms?: number;
  total_chunks_processed?: number;
  pre_rolls_injected?: number;
  ring_buffer_bytes?: number;
  last_wake_timestamp?: number;
  detector?: WakeWordDetectorMetrics;
  enabled?: boolean;
  ready?: boolean;
}

export interface StatusPayload {
  orb_state: OrbState;
  uptime_seconds: number;
  kernel_ready: boolean;
  live_connected: boolean;
  hermes_slow_ready: boolean;
  hermes_fast_ready: boolean;
  activation_state?: string;
  tasks?: TaskStatusPayload;
  key_rotator?: KeyRotatorStatus;
  delivery_queue?: DeliveryQueueStatus;
  wake_word?: WakeWordStatus;
}

export interface ConfigPayload {
  MODEL_LIVE?: string;
  MODEL_BRAIN?: string;
  MODEL_BRAIN_FAST?: string;
  VOICE_NAME?: string;
  ASSISTANT_NAME?: string;
  USER_NAME?: string;
  GEMINI_API_KEY?: string;
  GOOGLE_API_KEY?: string;
  FAST_BRAIN_TIMEOUT_SECONDS?: string;
  FAST_BRAIN_MAX_PARALLEL?: string;
  LIVE_VAD_SILENCE_DURATION_MS?: string;
  LIVE_VAD_PREFIX_PADDING_MS?: string;
  LIVE_VAD_START_SENSITIVITY?: string;
  LIVE_VAD_END_SENSITIVITY?: string;
  ENABLE_MUSIC_TOOL?: string;
  MIC_NOISE_GATE_ENABLED?: string;
  WAKE_WORD_ENABLED?: string;
  WAKE_WORD_MODEL?: string;
  WAKE_WORD_THRESHOLD?: string;
  WAKE_WORD_CONSECUTIVE_FRAMES?: string;
  WAKE_WORD_PRE_ROLL_MS?: string;
  WAKE_WORD_COOLDOWN_SECONDS?: string;
  HERMES_PLATFORM?: string;
  HERMES_ENABLED_TOOLSETS?: string;
  HERMES_DISABLED_TOOLSETS?: string;
  [key: string]: string | undefined;
}

export interface LogEntry {
  ts: number;
  level: "INFO" | "WARNING" | "ERROR" | "DEBUG";
  source: string;
  message: string;
}

export interface HermesMCP {
  name: string;
  command: string;
  args: string[];
  url: string;
  timeout: number;
}

export interface HermesToolsets {
  enabled: string[];
  disabled: string[];
  platform: string;
}

// WebSocket event types
export interface WSEvent {
  type: "state_change" | "task_update" | "log_entry";
  ts: number;
  data: unknown;
}
