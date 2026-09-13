import React, { useState, useEffect, useRef } from "react";
import { useJarvisStore } from "../store/jarvisStore";
import { jarvisAPI } from "../hooks/useJarvisAPI";
import { HermesCockpitTab } from "../components/panel/HermesCockpitTab";

// ── Warp Component Helpers ───────────────────────────────────────────────────
function WarpStatusDot({ active, color = "#22c55e" }: { active: boolean; color?: string }) {
  return (
    <span
      className="inline-block w-2 h-2 rounded-full shrink-0 transition-colors duration-300"
      style={{
        backgroundColor: active ? color : "#454545",
      }}
    />
  );
}

function WarpSectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-[10px] font-mono tracking-[2px] text-[#868584] uppercase mb-4 select-none">
      {children}
    </div>
  );
}

function WarpCard({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`bg-[#161618] border border-white/[0.08] rounded-xl p-5 shadow-sm ${className}`}>
      {children}
    </div>
  );
}

function WarpStatRow({ label, value, color }: { label: string; value: React.ReactNode; color?: string }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-white/[0.04] last:border-0">
      <span className="text-[11px] font-mono tracking-[1px] text-[#868584] uppercase">{label}</span>
      <span className="text-xs font-mono tabular-nums text-[#faf9f6]" style={color ? { color } : {}}>
        {value}
      </span>
    </div>
  );
}

import { VoiceAudioConfigTab } from "../components/panel/VoiceAudioConfigTab";
import { WakeWordConfigTab } from "../components/panel/WakeWordConfigTab";
import { IdentityConfigTab } from "../components/panel/IdentityConfigTab";
import { CredentialsBudgetTab } from "../components/panel/CredentialsBudgetTab";

// ── Tabs Config ──────────────────────────────────────────────────────────────
export type PanelTab =
  // Monitor & Salud
  | "dashboard"
  | "logs"
  | "acciones"
  // Jarvis Config
  | "config_voice"
  | "config_wakeword"
  | "config_identity"
  | "config_credentials"
  // Hermes Core
  | "hermes"
  | "hermes_chat"
  | "hermes_tasks"
  | "hermes_skills"
  | "hermes_memory"
  | "hermes_mcps"
  | "hermes_cron"
  | "hermes_autonomy"
  | "hermes_settings"
  // Fallbacks
  | "config"
  | "tareas";

interface SidebarGroup {
  category: string;
  items: {
    key: PanelTab;
    label: string;
  }[];
}

const SIDEBAR_GROUPS: SidebarGroup[] = [
  {
    category: "MONITOR & DIAGNÓSTICO",
    items: [
      { key: "dashboard", label: "Dashboard General" },
      { key: "logs", label: "Logs del Sistema" },
      { key: "acciones", label: "Acciones Rápidas" },
    ],
  },
  {
    category: "SISTEMA JARVIS",
    items: [
      { key: "config_voice", label: "Voz & Audio Multimodal" },
      { key: "config_wakeword", label: "Wake Word & Reposo" },
      { key: "config_identity", label: "Identidad & Personalidad" },
      { key: "config_credentials", label: "Claves & Presupuestos" },
    ],
  },
  {
    category: "AGENTE HERMES CORE",
    items: [
      { key: "hermes_chat", label: "Consola & Chat" },
      { key: "hermes_tasks", label: "Registro de Tareas" },
      { key: "hermes_skills", label: "Skills Nativas (12+)" },
      { key: "hermes_memory", label: "Memoria & Identidad" },
      { key: "hermes_mcps", label: "Toolsets & Servidores MCP" },
      { key: "hermes_cron", label: "Automatizaciones Cron" },
      { key: "hermes_autonomy", label: "Autonomía & Sentinel" },
      { key: "hermes_settings", label: "Directivas Operativas" },
    ],
  },
];

export interface VoiceOption {
  id: string;
  name: string;
  gender: "Femenina" | "Masculina";
  tone: string;
  badge?: string;
}

export const AVAILABLE_VOICES: VoiceOption[] = [
  { id: "Aoede", name: "Aoede", gender: "Femenina", tone: "Clara, equilibrada y natural", badge: "Default" },
  { id: "Charon", name: "Charon", gender: "Masculina", tone: "Grave, pausada y autoritaria" },
  { id: "Fenrir", name: "Fenrir", gender: "Masculina", tone: "Fuerte, profunda y segura" },
  { id: "Kore", name: "Kore", gender: "Femenina", tone: "Suave, calmada y reflexiva" },
  { id: "Puck", name: "Puck", gender: "Masculina", tone: "Enérgica, juvenil y entusiasta" },
  { id: "Leda", name: "Leda", gender: "Femenina", tone: "Expresiva, vivaz y amigable" },
  { id: "Orus", name: "Orus", gender: "Masculina", tone: "Cálida, resonante y firme" },
  { id: "Zephyr", name: "Zephyr", gender: "Femenina", tone: "Sutil, relajada y conversacional" },
];

export interface ModelOption {
  id: string;
  name: string;
  description: string;
  badge?: string;
  speed: string;
}

export const AVAILABLE_MODELS_LIVE: ModelOption[] = [
  {
    id: "gemini-3.1-flash-live-preview",
    name: "Gemini 3.1 Flash Live",
    description: "Recomendado oficial. Máxima inteligencia conversacional en tiempo real y baja latencia.",
    badge: "Recomendado",
    speed: "Ultra-rápido",
  },
  {
    id: "gemini-2.5-flash-native-audio-latest",
    name: "Gemini 2.5 Flash Native Audio",
    description: "Audio nativo de alta fidelidad, siempre en el último build estable de Google.",
    badge: "Estable",
    speed: "Ultra-rápido",
  },
  {
    id: "gemini-2.5-flash-native-audio-preview-12-2025",
    name: "2.5 Flash Native Audio (Dic 2025)",
    description: "Snapshot de diciembre 2025 del modelo native audio. Predecible y probado.",
    speed: "Ultra-rápido",
  },
  {
    id: "gemini-2.5-flash-native-audio-preview-09-2025",
    name: "2.5 Flash Native Audio (Sep 2025)",
    description: "Snapshot de septiembre 2025. Excelente estabilidad en conexiones lentas.",
    speed: "Rápido",
  },
];

export const AVAILABLE_MODELS_BRAIN: ModelOption[] = [
  {
    id: "gemini-3.1-flash-lite",
    name: "Gemini 3.1 Flash Lite",
    description: "Excelente balance para razonamiento autonomo. El mas eficiente de la familia 3.x.",
    badge: "Recomendado",
    speed: "Rapido",
  },
  {
    id: "gemini-3.1-pro-preview",
    name: "Gemini 3.1 Pro Preview",
    description: "Maximo razonamiento de la generacion 3.1. Para tareas criticas y codigo complejo.",
    badge: "Mas Potente",
    speed: "Profundo",
  },
  {
    id: "gemini-3.1-flash-lite-preview",
    name: "Gemini 3.1 Flash Lite Preview",
    description: "Preview del Flash Lite 3.1 — acceso anticipado a mejoras antes del lanzamiento estable.",
    speed: "Rapido",
  },
  {
    id: "gemini-3.8-flash",
    name: "Gemini 3.8 Flash",
    description: "Flash de ultima generacion con capacidades extendidas de tooluse y contexto.",
    badge: "Nuevo",
    speed: "Rapido",
  },
  {
    id: "gemini-3.7-flash",
    name: "Gemini 3.7 Flash",
    description: "Gran equilibrio entre razonamiento profundo y costo de cuota.",
    speed: "Rapido",
  },
  {
    id: "gemini-3.6-flash",
    name: "Gemini 3.6 Flash",
    description: "Generacion intermedia Flash, probada en produccion.",
    speed: "Rapido",
  },
  {
    id: "gemini-2.5-pro",
    name: "Gemini 2.5 Pro",
    description: "Profundidad analitica maxima, codigo complejo y tareas multi-paso de larga duracion.",
    speed: "Profundo",
  },
  {
    id: "gemini-2.5-flash",
    name: "Gemini 2.5 Flash",
    description: "Flash multimodal de segunda generacion — ventana de contexto amplia y herramientas.",
    speed: "Rapido",
  },
];

export const AVAILABLE_MODELS_BRAIN_FAST: ModelOption[] = [
  {
    id: "gemini-3.1-flash-lite",
    name: "Gemini 3.1 Flash Lite",
    description: "Consumo minimo de cuota y maxima velocidad para el carril rapido de Hermes.",
    badge: "Recomendado",
    speed: "Ultra-rapido",
  },
  {
    id: "gemini-3.8-flash",
    name: "Gemini 3.8 Flash",
    description: "Flash de ultima generacion. Ideal cuando necesitas mas precision en el fast-lane.",
    badge: "Nuevo",
    speed: "Rapido",
  },
  {
    id: "gemini-3.7-flash",
    name: "Gemini 3.7 Flash",
    description: "Generacion previa de Flash — probada y confiable para soporte en vivo.",
    speed: "Rapido",
  },
  {
    id: "gemini-3.5-flash",
    name: "Gemini 3.5 Flash",
    description: "Flash compacto con buen balance para consultas simples y busquedas.",
    speed: "Rapido",
  },
  {
    id: "gemini-3.5-flash-lite",
    name: "Gemini 3.5 Flash Lite",
    description: "Version lite de 3.5 — maxima economia de cuota para el carril paralelo.",
    badge: "Economico",
    speed: "Ultra-rapido",
  },
  {
    id: "gemini-2.5-flash-lite",
    name: "Gemini 2.5 Flash Lite",
    description: "Flash Lite de segunda generacion. Ideal para respuestas paralelas masivas.",
    speed: "Ultra-rapido",
  },
  {
    id: "gemini-2.5-flash",
    name: "Gemini 2.5 Flash",
    description: "Flash multimodal con contexto amplio para soporte de consultas largas.",
    speed: "Rapido",
  },
];

function CollapsibleModelSelector({
  title,
  subtitle,
  value,
  options,
  isOpen,
  onToggle,
  onChange,
  accentColor = "cyan",
}: {
  title: string;
  subtitle: string;
  value: string;
  options: ModelOption[];
  isOpen: boolean;
  onToggle: () => void;
  onChange: (val: string) => void;
  accentColor?: "cyan" | "purple" | "blue";
}) {
  const matched = options.find((o) => o.id.toLowerCase() === (value || "").toLowerCase());
  const dotColor =
    accentColor === "purple"
      ? "bg-purple-400 shadow-[0_0_8px_#c084fc]"
      : accentColor === "blue"
      ? "bg-sky-400 shadow-[0_0_8px_#38bdf8]"
      : "bg-cyan-400 shadow-[0_0_8px_#22d3ee]";

  const activeCardBorder =
    accentColor === "purple"
      ? "bg-purple-950/25 border-purple-500/50 text-[#faf9f6]"
      : accentColor === "blue"
      ? "bg-sky-950/25 border-sky-500/50 text-[#faf9f6]"
      : "bg-cyan-950/25 border-cyan-500/50 text-[#faf9f6]";

  const activeCheckBg =
    accentColor === "purple"
      ? "border-purple-400 bg-purple-400"
      : accentColor === "blue"
      ? "border-sky-400 bg-sky-400"
      : "border-cyan-400 bg-cyan-400";

  const btnText =
    accentColor === "purple"
      ? "text-purple-300 hover:text-purple-200"
      : accentColor === "blue"
      ? "text-sky-300 hover:text-sky-200"
      : "text-cyan-300 hover:text-cyan-200";

  return (
    <div className="space-y-3">
      {/* Label estático (sin botón extra) */}
      <div>
        <label className="block text-[11px] font-mono text-[#868584] uppercase">{title}</label>
        <span className="text-[10px] text-[#868584]">{subtitle}</span>
      </div>

      {/* Barra de modelo actual */}
      <div
        onClick={onToggle}
        className="w-full p-3 bg-[#111113] hover:bg-[#151518] border border-white/[0.08] hover:border-white/[0.15] rounded-xl flex items-center justify-between transition cursor-pointer"
      >
        <div className="flex items-center gap-3">
          <span className={`w-2.5 h-2.5 rounded-full ${dotColor}`} />
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono font-bold text-[#faf9f6]">
                {matched ? matched.name : value || "Sin configurar"}
              </span>
              {matched?.badge && (
                <span className="text-[9px] font-mono px-2 py-0.5 rounded bg-emerald-950/40 text-emerald-300 border border-emerald-500/20">
                  {matched.badge}
                </span>
              )}
              {matched?.speed && (
                <span className="text-[9px] font-mono px-2 py-0.5 rounded bg-white/[0.05] text-[#868584] border border-white/[0.06]">
                  {matched.speed}
                </span>
              )}
            </div>
            <div className="text-[11px] text-[#868584] mt-0.5">
              {matched ? matched.description : value}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 text-xs font-mono text-[#868584]">
          <span>{isOpen ? "Cerrar" : "Cambiar"}</span>
          <span className="text-[10px]">{isOpen ? "▲" : "▼"}</span>
        </div>
      </div>

      {/* Catálogo colapsable */}
      {isOpen && (
        <div className="p-4 bg-[#111113] border border-white/[0.08] rounded-xl space-y-3 animate-fade-in">
          <div className="flex items-center justify-between text-[10px] font-mono text-[#868584] uppercase tracking-wider">
            <span>Modelos Compatibles ({options.length})</span>
            <span>Haz clic para seleccionar</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            {options.map((opt) => {
              const isSelected = (value || "").toLowerCase() === opt.id.toLowerCase();
              return (
                <div
                  key={opt.id}
                  onClick={() => onChange(opt.id)}
                  className={`p-3 rounded-xl border transition cursor-pointer flex items-center justify-between ${
                    isSelected
                      ? activeCardBorder
                      : "bg-[#161618] border-white/[0.05] hover:border-white/[0.14] text-[#afaeac]"
                  }`}
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono font-bold text-[#faf9f6]">
                        {opt.name}
                      </span>
                      {opt.badge && (
                        <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-emerald-950/40 text-emerald-300 border border-emerald-500/20">
                          {opt.badge}
                        </span>
                      )}
                      <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-white/[0.05] text-[#868584]">
                        {opt.speed}
                      </span>
                    </div>
                    <div className="text-[11px] text-[#868584] leading-relaxed">
                      {opt.description}
                    </div>
                  </div>

                  <div className="pl-3 shrink-0">
                    <span
                      className={`w-4 h-4 rounded-full border flex items-center justify-center text-[10px] ${
                        isSelected
                          ? `${activeCheckBg} text-black font-bold`
                          : "border-white/[0.2]"
                      }`}
                    >
                      {isSelected ? "✓" : ""}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Campo manual */}
          <div className="pt-3 border-t border-white/[0.06] flex items-center justify-between gap-3">
            <span className="text-[10px] font-mono text-[#868584]">
              O escribe un identificador de modelo personalizado:
            </span>
            <input
              type="text"
              value={value || ""}
              onChange={(e) => onChange(e.target.value)}
              placeholder="gemini-..."
              className="h-8 bg-[#161618] border border-white/[0.08] focus:border-white/[0.25] rounded-lg px-3 text-xs font-mono text-[#faf9f6] outline-none max-w-[240px]"
            />
          </div>
        </div>
      )}
    </div>
  );
}

export function PanelView() {
  const status = useJarvisStore((s) => s.status);
  const tasks = useJarvisStore((s) => s.tasks);
  const config = useJarvisStore((s) => s.config);
  const storeLogs = useJarvisStore((s) => s.logs);
  const setConfig = useJarvisStore((s) => s.setConfig);
  const appendLog = useJarvisStore((s) => s.appendLog);
  const setActiveView = useJarvisStore((s) => s.setActiveView);
  const activePanelTab = useJarvisStore((s) => s.activePanelTab);
  const setActivePanelTab = useJarvisStore((s) => s.setActivePanelTab);

  const [activeTab, setActiveTab] = useState<PanelTab>(
    (activePanelTab as PanelTab) || "dashboard"
  );

  useEffect(() => {
    if (activePanelTab) {
      setActiveTab(activePanelTab as PanelTab);
    }
  }, [activePanelTab]);

  const [formData, setFormData] = useState<Record<string, string>>({});
  const [saveStatus, setSaveStatus] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, string>>({});
  const [hermesInfo, setHermesInfo] = useState<{ mcps: any[]; toolsets: any } | null>(null);
  const [capabilities, setCapabilities] = useState<any>(null);
  const [isVoicePickerOpen, setIsVoicePickerOpen] = useState<boolean>(false);
  const [isModelLiveOpen, setIsModelLiveOpen] = useState<boolean>(false);
  const [isModelBrainOpen, setIsModelBrainOpen] = useState<boolean>(false);
  const [isModelFastOpen, setIsModelFastOpen] = useState<boolean>(false);
  const [quickActionStatus, setQuickActionStatus] = useState<string | null>(null);
  const [quickActionPending, setQuickActionPending] = useState<string | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);

  // Sync config
  useEffect(() => {
    if (config) {
      const clean: Record<string, string> = {};
      Object.keys(config).forEach((k) => { clean[k] = config[k] || ""; });
      setFormData(clean);
    }
  }, [config]);

  // Initial logs
  useEffect(() => {
    async function syncLogs() {
      try {
        const res = await jarvisAPI.getLogs(60);
        res.logs.forEach((log) => appendLog(log));
      } catch {}
    }
    if (storeLogs.length === 0) syncLogs();
  }, [appendLog, storeLogs.length]);

  // Hermes metadata
  useEffect(() => {
    if (activeTab === "hermes" && !hermesInfo) {
      Promise.all([jarvisAPI.getHermesMCPs(), jarvisAPI.getHermesToolsets()])
        .then(([mcps, toolsets]) => setHermesInfo({ mcps: mcps.mcps, toolsets }))
        .catch(() => {});
    }
    if (activeTab === "hermes" && !capabilities) {
      jarvisAPI.getCapabilities()
        .then(setCapabilities)
        .catch(() => {});
    }
  }, [activeTab, hermesInfo, capabilities]);

  const handleInputChange = (key: string, val: string) => {
    setFormData((prev) => ({ ...prev, [key]: val }));
  };

  const [isSaving, setIsSaving] = useState<boolean>(false);

  const runQuickAction = async (name: string, action: () => Promise<unknown>) => {
    setQuickActionPending(name);
    setQuickActionStatus(null);
    try {
      await action();
      setQuickActionStatus(`${name}: completado`);
    } catch (err: unknown) {
      const detail = err instanceof Error ? err.message : String(err);
      setQuickActionStatus(`${name}: ${detail || "falló la operación"}`);
    } finally {
      setQuickActionPending(null);
    }
  };

  const handleDirectSave = async () => {
    setIsSaving(true);
    setSaveStatus("Guardando en .env...");
    try {
      const updates: Record<string, string> = {};
      Object.keys(formData).forEach((k) => {
        if (formData[k] !== config?.[k]) updates[k] = formData[k];
      });
      if (Object.keys(updates).length === 0) {
        setSaveStatus("No hay cambios pendientes");
        setTimeout(() => setSaveStatus(null), 2000);
        setIsSaving(false);
        return;
      }
      await jarvisAPI.updateConfig(updates);
      const fresh = await jarvisAPI.getConfig();
      setConfig(fresh);
      setSaveStatus(`✓ ${Object.keys(updates).length} parámetro(s) actualizados`);
    } catch (err: unknown) {
      setSaveStatus(`Error: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setIsSaving(false);
      setTimeout(() => setSaveStatus(null), 3500);
    }
  };

  const handleSaveConfig = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    await handleDirectSave();
  };

  const runTest = async (name: string, fn: () => Promise<any>) => {
    setTestResults((p) => ({ ...p, [name]: "Running..." }));
    try {
      const res = await fn();
      const ok = res.status === "ok" || res.status === "connected" || res.live_connected;
      setTestResults((p) => ({ ...p, [name]: ok ? "Passed" : `Failed: ${res.error || res.message || "Error"}` }));
    } catch (e: any) {
      setTestResults((p) => ({ ...p, [name]: `Failed: ${e.message}` }));
    }
    setTimeout(() => setTestResults((p) => { const n = { ...p }; delete n[name]; return n; }), 5000);
  };

  useEffect(() => {
    if (activeTab === "logs") logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [storeLogs.length, activeTab]);

  const uptimeStr = status?.uptime_seconds
    ? `${Math.floor(status.uptime_seconds / 3600)}h ${Math.floor((status.uptime_seconds % 3600) / 60)}m`
    : "—";

  return (
    <div
      className="fixed inset-0 w-screen h-screen flex z-50 select-none text-[#afaeac]"
      style={{ backgroundColor: "#0c0c0e" }}
    >
      {/* ── LEFT WORKBENCH SIDEBAR ── */}
      <aside className="w-[260px] shrink-0 h-full flex flex-col bg-[#121214] border-r border-white/[0.08] px-5 py-6">
        {/* Brand */}
        <div className="flex items-center gap-3 px-3 py-4 mb-6 border-b border-white/[0.06]">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 shadow-[0_0_8px_#34d399]" />
          <div>
            <div className="text-xs font-mono font-bold tracking-[2px] text-[#faf9f6] uppercase">JARVIS WORKBENCH</div>
            <div className="text-[10px] font-mono text-[#868584] mt-1">Centro de Control Autónomo</div>
          </div>
        </div>

        {/* Navigation Tabs (Grouped) */}
        <nav className="space-y-4 flex-1 overflow-y-auto pr-1">
          {SIDEBAR_GROUPS.map((group) => (
            <div key={group.category} className="space-y-1">
              <div className="text-[9px] font-mono tracking-[1.5px] text-[#868584] uppercase px-3 py-1 select-none">
                {group.category}
              </div>
              {group.items.map((tab) => {
                const isSelected =
                  activeTab === tab.key || (tab.key === "hermes_chat" && activeTab === "hermes");
                const isHermes = tab.key.startsWith("hermes");
                return (
                  <button
                    key={tab.key}
                    onClick={() => {
                      setActiveTab(tab.key);
                      setActivePanelTab(tab.key);
                    }}
                    className={`w-full flex items-center justify-between px-3.5 py-2 text-[12px] font-medium rounded-xl transition cursor-pointer ${
                      isSelected
                        ? "bg-[#222226] text-[#faf9f6] shadow-sm border border-white/[0.08]"
                        : "text-[#868584] hover:text-[#afaeac] hover:bg-white/[0.03] border border-transparent"
                    }`}
                  >
                    <span className="flex items-center gap-2.5">
                      <span
                        className={`w-1.5 h-1.5 rounded-full transition-colors ${
                          isHermes
                            ? isSelected
                              ? "bg-purple-400"
                              : "bg-purple-500/40"
                            : isSelected
                            ? "bg-cyan-400"
                            : "bg-white/20"
                        }`}
                      />
                      <span>{tab.label}</span>
                    </span>
                    {tab.key === "logs" && storeLogs.length > 0 && (
                      <span className="text-[10px] font-mono text-[#868584] bg-white/[0.05] px-2 py-0.5 rounded-full">
                        {storeLogs.length}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          ))}
        </nav>

        {/* Bottom Nav / Return */}
        <div className="pt-5 mt-2 border-t border-white/[0.06] space-y-2">
          <button
            onClick={() => setActiveView("orb")}
            className="w-full flex items-center justify-center gap-2.5 px-4 py-2.5 text-[13px] font-medium text-[#afaeac] hover:text-[#faf9f6] bg-[#1c1c1f] hover:bg-[#252528] border border-white/[0.06] rounded-xl transition cursor-pointer"
          >
            <span>←</span>
            <span>Volver al Orbe</span>
          </button>
          <div className="text-center text-[9px] font-mono text-[#454545] mt-1">JARVIS v2.0 · localhost:8000</div>
        </div>
      </aside>

      {/* ── RIGHT MAIN WORKSPACE ── */}
      <main className="flex-1 h-full overflow-y-auto p-8 select-text">
        <div className="max-w-4xl mx-auto space-y-6">

          {/* ════════ DASHBOARD ════════ */}
          {activeTab === "dashboard" && (
            <div className="space-y-5">

              {/* Header de salud del sistema */}
              <div className="flex items-center justify-between">
                <div>
                  <h1 className="text-base font-bold text-[#faf9f6] tracking-tight">Panel de Control</h1>
                  <p className="text-[11px] text-[#868584] mt-0.5">Telemetría en tiempo real del núcleo JARVIS</p>
                </div>
                <button
                  onClick={async () => {
                    try { const s = await jarvisAPI.getStatus(); useJarvisStore.getState().setStatus(s); } catch {}
                  }}
                  className="flex items-center gap-2 px-3 py-1.5 text-[11px] font-mono text-[#868584] hover:text-[#afaeac] bg-[#1c1c1f] hover:bg-[#222226] border border-white/[0.06] rounded-lg transition cursor-pointer"
                >
                  <span>↻</span>
                  <span>Actualizar</span>
                </button>
              </div>

              {/* Telemetry Grid — 4 indicadores principales */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                <WarpCard>
                  <WarpSectionLabel>Núcleo Principal</WarpSectionLabel>
                  <div className="flex items-center gap-2 mt-0.5">
                    <WarpStatusDot active={!!status?.kernel_ready} color="#22c55e" />
                    <span className="text-sm font-semibold text-[#faf9f6]">{status?.kernel_ready ? "Operativo" : "Desconectado"}</span>
                  </div>
                  <div className="text-[11px] font-mono tabular-nums text-[#868584] mt-1.5">Activo: {uptimeStr}</div>
                </WarpCard>

                <WarpCard>
                  <WarpSectionLabel>Voz en Vivo</WarpSectionLabel>
                  <div className="flex items-center gap-2 mt-0.5">
                    <WarpStatusDot active={!!status?.live_connected} color="#38bdf8" />
                    <span className="text-sm font-semibold text-[#faf9f6]">{status?.live_connected ? "Conectado" : "Desconectado"}</span>
                  </div>
                  <div className="text-[11px] font-mono text-[#868584] mt-1.5">Gemini Live Link</div>
                </WarpCard>

                <WarpCard>
                  <WarpSectionLabel>Hermes Lento</WarpSectionLabel>
                  <div className="flex items-center gap-2 mt-0.5">
                    <WarpStatusDot active={!!status?.hermes_slow_ready} color="#f59e0b" />
                    <span className="text-sm font-semibold text-[#faf9f6]">{status?.hermes_slow_ready ? "Activo" : "No disponible"}</span>
                  </div>
                  <div className="text-[11px] font-mono text-[#868584] mt-1.5">Razonamiento Profundo</div>
                </WarpCard>

                <WarpCard>
                  <WarpSectionLabel>Hermes Rápido</WarpSectionLabel>
                  <div className="flex items-center gap-2 mt-0.5">
                    <WarpStatusDot active={!!status?.hermes_fast_ready} color="#a855f7" />
                    <span className="text-sm font-semibold text-[#faf9f6]">{status?.hermes_fast_ready ? "Activo" : "No disponible"}</span>
                  </div>
                  <div className="text-[11px] font-mono text-[#868584] mt-1.5">Carril Paralelo Rápido</div>
                </WarpCard>
              </div>

              {/* Panel de detalles: Key Rotator + Wake Word */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-3.5">
                <WarpCard>
                  <WarpSectionLabel>Sistema de Rotación de Claves</WarpSectionLabel>
                  {status?.key_rotator ? (
                    <>
                      <WarpStatRow label="Pool de Claves Activo" value={`${status.key_rotator.pool_size} claves`} />
                      <WarpStatRow label="Invocaciones Totales" value={status.key_rotator.call_count} />
                      <WarpStatRow label="Clave Activa Actual" value={status.key_rotator.active_key_masked} color="#38bdf8" />
                    </>
                  ) : (
                    <div className="text-xs text-[#868584] italic">Rotador no cargado</div>
                  )}
                </WarpCard>

                <WarpCard>
                  <WarpSectionLabel>Wake Word & Puerta de Activación</WarpSectionLabel>
                  <WarpStatRow
                    label="Estado Wake"
                    value={
                      <span className="flex items-center gap-2">
                        <WarpStatusDot active={status?.wake_word?.wake_word_enabled !== false} color="#22c55e" />
                        <span>{status?.wake_word?.wake_word_enabled !== false ? "Armado" : "Desarmado"}</span>
                      </span>
                    }
                  />
                  <WarpStatRow label="Puerta de Activación" value={status?.activation_state || "—"} />
                  <WarpStatRow label="Perfil del Orbe" value={status?.orb_state || "—"} color="#faf9f6" />
                </WarpCard>
              </div>

              {/* Acciones rápidas directas desde dashboard */}
              <WarpCard>
                <WarpSectionLabel>Acciones Rápidas del Sistema</WarpSectionLabel>
                <div className="flex flex-wrap gap-2.5 items-center">
                  <button
                    onClick={() => runQuickAction("Micrófono", () => jarvisAPI.toggleMute())}
                    disabled={quickActionPending !== null}
                    className="px-3.5 py-1.5 text-xs font-medium text-[#afaeac] hover:text-[#faf9f6] bg-[#222224] hover:bg-[#2d2d30] border border-white/[0.08] rounded-full transition cursor-pointer disabled:opacity-50"
                  >
                    {quickActionPending === "Micrófono" ? "Procesando..." : "⏺ Micrófono"}
                  </button>
                  <button
                    onClick={() => runQuickAction("Sesión Live", () => jarvisAPI.restartVoice())}
                    disabled={quickActionPending !== null}
                    className="px-3.5 py-1.5 text-xs font-medium text-[#afaeac] hover:text-[#faf9f6] bg-[#222224] hover:bg-[#2d2d30] border border-white/[0.08] rounded-full transition cursor-pointer disabled:opacity-50"
                  >
                    {quickActionPending === "Sesión Live" ? "Procesando..." : "↺ Reiniciar Voz"}
                  </button>
                  <button
                    onClick={() => runQuickAction("Activación del núcleo", () => jarvisAPI.wake())}
                    disabled={quickActionPending !== null}
                    className="px-3.5 py-1.5 text-xs font-medium text-[#afaeac] hover:text-[#faf9f6] bg-[#222224] hover:bg-[#2d2d30] border border-white/[0.08] rounded-full transition cursor-pointer disabled:opacity-50"
                  >
                    {quickActionPending === "Activación del núcleo" ? "Procesando..." : "▶ Despertar"}
                  </button>
                  <button
                    onClick={() => runQuickAction("Reposo del núcleo", () => jarvisAPI.sleep())}
                    disabled={quickActionPending !== null}
                    className="px-3.5 py-1.5 text-xs font-medium text-[#afaeac] hover:text-[#faf9f6] bg-[#222224] hover:bg-[#2d2d30] border border-white/[0.08] rounded-full transition cursor-pointer disabled:opacity-50"
                  >
                    {quickActionPending === "Reposo del núcleo" ? "Procesando..." : "⏸ Reposo"}
                  </button>
                  <button
                    onClick={() => runQuickAction("Interrupción de tarea", () => jarvisAPI.cancelTask())}
                    disabled={quickActionPending !== null}
                    className="px-3.5 py-1.5 text-xs font-medium text-amber-300/80 hover:text-amber-200 bg-amber-950/20 hover:bg-amber-900/30 border border-amber-500/20 rounded-full transition cursor-pointer disabled:opacity-50"
                  >
                    {quickActionPending === "Interrupción de tarea" ? "Procesando..." : "⏹ Interrumpir Tarea"}
                  </button>
                  {quickActionStatus && (
                    <span className={`text-xs font-mono px-3 py-1 rounded-full border ${
                      quickActionStatus.includes(": completado")
                        ? "bg-emerald-950/40 border-emerald-500/30 text-emerald-300"
                        : "bg-red-950/40 border-red-500/30 text-red-300"
                    }`}>
                      {quickActionStatus}
                    </span>
                  )}
                </div>
              </WarpCard>

              {/* Barra de diagnósticos */}
              <WarpCard>
                <WarpSectionLabel>Diagnósticos & Validación del Pipeline</WarpSectionLabel>
                <div className="flex flex-wrap gap-2.5 items-center">
                  <button
                    onClick={() => runTest("voz-en-vivo", jarvisAPI.testLive)}
                    className="px-3.5 py-1.5 text-xs font-medium text-[#afaeac] hover:text-[#faf9f6] bg-[#222224] hover:bg-[#2d2d30] border border-white/[0.08] rounded-full transition cursor-pointer"
                  >
                    Probar Sesión en Vivo
                  </button>
                  <button
                    onClick={() => runTest("hermes-lento", jarvisAPI.testHermesSlow)}
                    className="px-3.5 py-1.5 text-xs font-medium text-[#afaeac] hover:text-[#faf9f6] bg-[#222224] hover:bg-[#2d2d30] border border-white/[0.08] rounded-full transition cursor-pointer"
                  >
                    Probar Hermes Lento
                  </button>
                  <button
                    onClick={() => runTest("hermes-rapido", jarvisAPI.testHermesFast)}
                    className="px-3.5 py-1.5 text-xs font-medium text-[#afaeac] hover:text-[#faf9f6] bg-[#222224] hover:bg-[#2d2d30] border border-white/[0.08] rounded-full transition cursor-pointer"
                  >
                    Probar Hermes Rápido
                  </button>

                  {Object.entries(testResults).map(([k, v]) => (
                    <span key={k} className={`text-xs font-mono px-3 py-1 rounded-full border ${v === "Passed" ? "bg-emerald-950/40 border-emerald-500/30 text-emerald-300" : v.startsWith("Failed") ? "bg-red-950/40 border-red-500/30 text-red-300" : "bg-[#222224] border-white/[0.08] text-[#868584]"}`}>
                      {k}: {v === "Passed" ? "OK" : v === "Running..." ? "Probando..." : v}
                    </span>
                  ))}
                </div>
              </WarpCard>
            </div>
          )}

          {/* ════════ TAREAS (alias legacy) ════════ */}
          {activeTab === "tareas" && (
            <div className="space-y-4">
              <WarpCard>
                <WarpSectionLabel>Hermes Carril Lento (Razonamiento Profundo)</WarpSectionLabel>
                {!tasks?.running_slow?.length ? (
                  <div className="text-xs text-[#868584] italic py-2">Sin tareas activas en el carril lento</div>
                ) : (
                  <div className="space-y-2">
                    {tasks.running_slow.map((t) => (
                      <div key={t.task_id} className="flex justify-between items-center p-3 bg-[#1e1e22] border border-white/[0.06] rounded-lg">
                        <div className="flex items-center gap-3">
                          <WarpStatusDot active color="#f59e0b" />
                          <span className="text-xs text-[#faf9f6] font-mono">{t.prompt}</span>
                        </div>
                        <span className="text-[11px] text-[#868584] font-mono">{t.task_id}</span>
                      </div>
                    ))}
                  </div>
                )}
              </WarpCard>

              <WarpCard>
                <WarpSectionLabel>Hermes Carril Rápido (Consultas Paralelas)</WarpSectionLabel>
                {!tasks?.running_fast?.length ? (
                  <div className="text-xs text-[#868584] italic py-2">Sin tareas activas en el carril rápido</div>
                ) : (
                  <div className="space-y-2">
                    {tasks.running_fast.map((t) => (
                      <div key={t.task_id} className="flex justify-between items-center p-3 bg-[#1e1e22] border border-white/[0.06] rounded-lg">
                        <div className="flex items-center gap-3">
                          <WarpStatusDot active color="#a855f7" />
                          <span className="text-xs text-[#faf9f6] font-mono">{t.prompt}</span>
                        </div>
                        <span className="text-[11px] text-[#868584] font-mono">{t.task_id}</span>
                      </div>
                    ))}
                  </div>
                )}
              </WarpCard>

              <WarpCard>
                <WarpSectionLabel>Registro de Ejecuciones Recientes</WarpSectionLabel>
                {!tasks?.recent?.length ? (
                  <div className="text-xs text-[#868584] italic py-2">El registro de ejecuciones está vacío</div>
                ) : (
                  <div className="space-y-1 font-mono text-xs">
                    {tasks.recent.slice(0, 15).map((t) => (
                      <div key={t.task_id} className="flex justify-between items-center py-2 px-3 hover:bg-white/[0.02] rounded-md transition border-b border-white/[0.03]">
                        <div className="flex items-center gap-3 truncate max-w-lg">
                          <span className={t.state === "completed" ? "text-emerald-400" : t.state === "failed" ? "text-red-400" : "text-[#868584]"}>
                            ● {t.state === "completed" ? "COMPLETADO" : t.state === "failed" ? "FALLIDO" : t.state?.toUpperCase()}
                          </span>
                          <span className="text-[#afaeac] truncate">{t.prompt}</span>
                        </div>
                        <span className="text-[10px] text-[#868584] shrink-0">{t.task_id}</span>
                      </div>
                    ))}
                  </div>
                )}
              </WarpCard>
            </div>
          )}

          {/* ════════ CONFIG: VOZ & AUDIO MULTIMODAL ════════ */}
          {(activeTab === "config_voice" || activeTab === "config") && (
            <VoiceAudioConfigTab
              formData={formData}
              onInputChange={handleInputChange}
              onSave={handleDirectSave}
              isSaving={isSaving}
              saveStatus={saveStatus}
            />
          )}

          {/* ════════ CONFIG: WAKE WORD & REPOSO ════════ */}
          {activeTab === "config_wakeword" && (
            <WakeWordConfigTab
              formData={formData}
              onInputChange={handleInputChange}
              onSave={handleDirectSave}
              isSaving={isSaving}
              saveStatus={saveStatus}
            />
          )}

          {/* ════════ CONFIG: IDENTIDAD & PERSONALIDAD ════════ */}
          {activeTab === "config_identity" && (
            <IdentityConfigTab
              formData={formData}
              onInputChange={handleInputChange}
              onSave={handleDirectSave}
              isSaving={isSaving}
              saveStatus={saveStatus}
            />
          )}

          {/* ════════ CONFIG: CLAVES & PRESUPUESTOS ════════ */}
          {activeTab === "config_credentials" && (
            <CredentialsBudgetTab
              formData={formData}
              onInputChange={handleInputChange}
              onSave={handleDirectSave}
              isSaving={isSaving}
              saveStatus={saveStatus}
            />
          )}

          {/* ════════ LOGS DEL SISTEMA ════════ */}
          {activeTab === "logs" && (
            <WarpCard className="h-[calc(100vh-100px)] flex flex-col bg-[#111113] border-white/[0.08]">
              <div className="flex justify-between items-center pb-3 mb-2 border-b border-white/[0.06]">
                <WarpSectionLabel>Flujo de Salida del Kernel</WarpSectionLabel>
                <button
                  onClick={() => useJarvisStore.getState().clearLogs()}
                  className="px-3.5 py-1 text-xs font-mono text-red-400/80 hover:text-red-300 bg-red-950/20 border border-red-500/20 rounded-full transition cursor-pointer"
                >
                  Limpiar Buffer
                </button>
              </div>
              <div className="flex-1 overflow-y-auto font-mono text-xs space-y-1 pr-2 min-h-0">
                {storeLogs.length === 0 ? (
                  <div className="text-[#868584] italic py-4">Sin eventos registrados en la sesión actual</div>
                ) : (
                  storeLogs.map((log, idx) => (
                    <div key={idx} className="flex items-start gap-3 py-1 px-2 hover:bg-white/[0.02] rounded transition leading-relaxed">
                      <span className="w-[72px] shrink-0 text-[11px] tabular-nums text-[#868584]">
                        {new Date(log.ts * 1000).toLocaleTimeString("es-MX", { hour12: false })}
                      </span>
                      <span className={`w-[58px] shrink-0 text-center text-[9px] font-bold uppercase rounded py-0.5 ${
                        log.level === "ERROR" ? "text-red-400 bg-red-950/40 border border-red-500/30"
                        : log.level === "WARNING" ? "text-amber-400 bg-amber-950/40 border border-amber-500/30"
                        : "text-[#afaeac] bg-[#222224] border border-white/[0.06]"
                      }`}>
                        {log.level}
                      </span>
                      <span className="w-[64px] shrink-0 text-[10px] text-[#868584] truncate">
                        [{log.source}]
                      </span>
                      <span className="flex-1 text-[#faf9f6] break-words">
                        {log.message}
                      </span>
                    </div>
                  ))
                )}
                <div ref={logsEndRef} />
              </div>
            </WarpCard>
          )}

          {/* ════════ HERMES AGENT (OPCIONES INTEGRADAS EN SIDEBAR) ════════ */}
          {activeTab.startsWith("hermes") && (
            <div className="h-[calc(100vh-140px)] flex flex-col min-h-0">
              <HermesCockpitTab
                subTab={
                  activeTab === "hermes"
                    ? "chat"
                    : (activeTab.replace("hermes_", "") as any)
                }
                hideHeaderBar={true}
              />
            </div>
          )}

          {/* ════════ ACCIONES RÁPIDAS ════════ */}
          {activeTab === "acciones" && (
            <div className="space-y-5">
              <div>
                <h1 className="text-base font-bold text-[#faf9f6] tracking-tight">Acciones Rápidas</h1>
                <p className="text-[11px] text-[#868584] mt-0.5">Control directo sobre el pipeline de voz y el núcleo del sistema</p>
              </div>

              {quickActionStatus && (
                <div
                  role="status"
                  className={`px-4 py-3 text-xs font-mono border rounded-lg ${
                    quickActionStatus.includes(": completado")
                      ? "text-emerald-300 bg-emerald-950/20 border-emerald-500/25"
                      : "text-red-300 bg-red-950/20 border-red-500/25"
                  }`}
                >
                  {quickActionStatus}
                </div>
              )}

              <WarpCard>
                <WarpSectionLabel>Control de Pipeline de Voz</WarpSectionLabel>
                <div className="flex flex-wrap gap-3">
                  <button
                    onClick={() => runQuickAction("Micrófono", () => jarvisAPI.toggleMute())}
                    disabled={quickActionPending !== null}
                    className="px-5 py-2.5 text-xs font-medium text-[#afaeac] hover:text-[#faf9f6] bg-[#222224] hover:bg-[#2d2d30] border border-white/[0.08] rounded-full transition cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {quickActionPending === "Micrófono" ? "Procesando..." : "⏺  Alternar Micrófono"}
                  </button>
                  <button
                    onClick={() => runQuickAction("Sesión Live", () => jarvisAPI.restartVoice())}
                    disabled={quickActionPending !== null}
                    className="px-5 py-2.5 text-xs font-medium text-[#afaeac] hover:text-[#faf9f6] bg-[#222224] hover:bg-[#2d2d30] border border-white/[0.08] rounded-full transition cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {quickActionPending === "Sesión Live" ? "Procesando..." : "↺  Reiniciar Sesión en Vivo"}
                  </button>
                </div>
              </WarpCard>

              <WarpCard>
                <WarpSectionLabel>Control de Estado del Núcleo</WarpSectionLabel>
                <div className="flex flex-wrap gap-3">
                  <button
                    onClick={() => runQuickAction("Activación del núcleo", () => jarvisAPI.wake())}
                    disabled={quickActionPending !== null}
                    className="px-5 py-2.5 text-xs font-medium text-[#afaeac] hover:text-[#faf9f6] bg-[#222224] hover:bg-[#2d2d30] border border-white/[0.08] rounded-full transition cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {quickActionPending === "Activación del núcleo" ? "Procesando..." : "▶  Despertar Kernel"}
                  </button>
                  <button
                    onClick={() => runQuickAction("Reposo del núcleo", () => jarvisAPI.sleep())}
                    disabled={quickActionPending !== null}
                    className="px-5 py-2.5 text-xs font-medium text-[#afaeac] hover:text-[#faf9f6] bg-[#222224] hover:bg-[#2d2d30] border border-white/[0.08] rounded-full transition cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {quickActionPending === "Reposo del núcleo" ? "Procesando..." : "⏸  Poner en Reposo"}
                  </button>
                  <button
                    onClick={() => runQuickAction("Interrupción de tarea", () => jarvisAPI.cancelTask())}
                    disabled={quickActionPending !== null}
                    className="px-5 py-2.5 text-xs font-medium text-amber-300/80 hover:text-amber-200 bg-amber-950/20 hover:bg-amber-900/30 border border-amber-500/20 rounded-full transition cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {quickActionPending === "Interrupción de tarea" ? "Procesando..." : "⏹  Interrumpir Tarea Activa"}
                  </button>
                </div>
              </WarpCard>

              {/* Diagnósticos también disponibles aquí */}
              <WarpCard>
                <WarpSectionLabel>Diagnósticos del Pipeline</WarpSectionLabel>
                <div className="flex flex-wrap gap-2.5 items-center">
                  <button
                    onClick={() => runTest("voz-en-vivo", jarvisAPI.testLive)}
                    className="px-3.5 py-1.5 text-xs font-medium text-[#afaeac] hover:text-[#faf9f6] bg-[#222224] hover:bg-[#2d2d30] border border-white/[0.08] rounded-full transition cursor-pointer"
                  >
                    Probar Sesión en Vivo
                  </button>
                  <button
                    onClick={() => runTest("hermes-lento", jarvisAPI.testHermesSlow)}
                    className="px-3.5 py-1.5 text-xs font-medium text-[#afaeac] hover:text-[#faf9f6] bg-[#222224] hover:bg-[#2d2d30] border border-white/[0.08] rounded-full transition cursor-pointer"
                  >
                    Probar Hermes Lento
                  </button>
                  <button
                    onClick={() => runTest("hermes-rapido", jarvisAPI.testHermesFast)}
                    className="px-3.5 py-1.5 text-xs font-medium text-[#afaeac] hover:text-[#faf9f6] bg-[#222224] hover:bg-[#2d2d30] border border-white/[0.08] rounded-full transition cursor-pointer"
                  >
                    Probar Hermes Rápido
                  </button>
                  {Object.entries(testResults).map(([k, v]) => (
                    <span key={k} className={`text-xs font-mono px-3 py-1 rounded-full border ${v === "Passed" ? "bg-emerald-950/40 border-emerald-500/30 text-emerald-300" : v.startsWith("Failed") ? "bg-red-950/40 border-red-500/30 text-red-300" : "bg-[#222224] border-white/[0.08] text-[#868584]"}`}>
                      {k}: {v === "Passed" ? "OK" : v === "Running..." ? "Probando..." : v}
                    </span>
                  ))}
                </div>
              </WarpCard>

              <WarpCard className="border-red-500/20 bg-red-950/10">
                <WarpSectionLabel>Zona Peligrosa</WarpSectionLabel>
                <p className="text-[11px] text-[#868584] mb-3">Esta acción termina el proceso del kernel de JARVIS de forma irreversible.</p>
                <button
                  onClick={async () => {
                    if (window.confirm("¿Estás seguro de que deseas terminar el proceso del núcleo de JARVIS? Esta acción es irreversible.")) {
                      runQuickAction("Cierre del núcleo", () => jarvisAPI.shutdown());
                    }
                  }}
                  disabled={quickActionPending !== null}
                  className="px-5 py-2.5 text-xs font-medium text-red-300 hover:text-red-200 bg-red-950/40 hover:bg-red-900/50 border border-red-500/30 rounded-full transition cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  ⚠ Terminar Proceso del Kernel
                </button>
              </WarpCard>
            </div>
          )}

        </div>
      </main>
    </div>
  );
}
