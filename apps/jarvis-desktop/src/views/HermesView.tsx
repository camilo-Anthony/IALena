import React, { useEffect, useState, useRef } from "react";
import { useJarvisStore } from "../store/jarvisStore";
import { jarvisAPI } from "../hooks/useJarvisAPI";
import type { TaskItem } from "../types";

type HermesTab = "chat" | "tasks" | "skills" | "mcps" | "autonomy" | "settings";

interface SkillInfo {
  name: string;
  description: string;
}

const ALL_POSSIBLE_TOOLSETS = [
  "web", "file", "terminal", "browser", "skills", "todo", "memory",
  "code_execution", "delegation", "cronjob", "vision", "image_gen", "tts", "computer_use"
];

const FALLBACK_SKILLS: SkillInfo[] = [
  { name: "software-development", description: "Desarrollo fullstack, refactorización de código, debugging y arquitecturas." },
  { name: "computer-use", description: "Automatización de GUI del sistema, clics, captura de pantalla y teclado nativo." },
  { name: "research", description: "Investigación web profunda, síntesis de papers, crawling y resúmenes estructurados." },
  { name: "data-science", description: "Análisis de datos, scripts de Python, visualizaciones y pipelines estadísticos." },
  { name: "autonomous-ai-agents", description: "Orquestación multi-agente, delegación jerárquica y resolución recursiva." },
  { name: "creative", description: "Modelado 3D (Blender), síntesis de audio, generación de imágenes y assets creativos." },
  { name: "social-media", description: "Búsqueda en X (Twitter), monitorización de tendencias y análisis de sentimiento." },
  { name: "productivity", description: "Gestión de tareas TODO, calendarios, notas persistentes y recordatorios." },
  { name: "smart-home", description: "Integración con Home Assistant, domótica y control de dispositivos locales." },
  { name: "media", description: "Procesamiento de video, transcripción whisper, visión por computadora y OCR." },
  { name: "github", description: "Gestión de repositorios, PRs, issues y revisiones de diffs en git." },
  { name: "note-taking", description: "Gestión de bitácoras, Markdown, Obsidian y base de conocimiento local." },
];

export function HermesView() {
  const setActiveView = useJarvisStore((s) => s.setActiveView);
  const [activeTab, setActiveTab] = useState<HermesTab>("chat");

  // Estados de Tareas
  const [tasks, setTasks] = useState<{
    running_slow: TaskItem[];
    running_fast: TaskItem[];
    pending_slow: TaskItem[];
    recent: TaskItem[];
  }>({
    running_slow: [],
    running_fast: [],
    pending_slow: [],
    recent: [],
  });

  // Estados de Despacho / Chat
  const [prompt, setPrompt] = useState("");
  const [selectedLane, setSelectedLane] = useState<"slow" | "fast">("slow");
  const [isDispatching, setIsDispatching] = useState(false);
  const [dispatchStatus, setDispatchStatus] = useState<string | null>(null);

  // Estados de Habilidades & MCPs
  const [skills, setSkills] = useState<SkillInfo[]>(FALLBACK_SKILLS);
  const [toolsets, setToolsets] = useState<string[]>(ALL_POSSIBLE_TOOLSETS);
  const [mcps, setMcps] = useState<Array<{ name: string; command?: string }>>([]);

  // Estados de Configuración Interactivas de Hermes
  const [cfgFastBrain, setCfgFastBrain] = useState("gemini-2.5-flash");
  const [cfgSlowBrain, setCfgSlowBrain] = useState("gemini-2.5-pro");
  const [cfgTimeout, setCfgTimeout] = useState(60);
  const [cfgEnabledToolsets, setCfgEnabledToolsets] = useState<string[]>(ALL_POSSIBLE_TOOLSETS);
  const [cfgApiKey, setCfgApiKey] = useState("");
  const [isSavingConfig, setIsSavingConfig] = useState(false);
  const [configSaveMsg, setConfigSaveMsg] = useState<string | null>(null);

  // Estados de Autonomía
  const [autonomyStatus, setAutonomyStatus] = useState<{
    scheduler?: { running: boolean; interval_seconds: number; total_jobs_executed: number };
    sentinel?: { running: boolean; battery?: { percent: number; power_plugged: boolean } };
  }>({});

  const [taskFilter, setTaskFilter] = useState<"all" | "running" | "completed">("all");
  const [expandedTaskId, setExpandedTaskId] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Carga inicial y polling periódico (cada 3.5s)
  useEffect(() => {
    let active = true;

    async function syncData() {
      try {
        const [tasksRes, autoRes] = await Promise.all([
          jarvisAPI.getHermesTasks(),
          jarvisAPI.getAutonomyStatus(),
        ]);
        if (active) {
          setTasks(tasksRes);
          setAutonomyStatus(autoRes);
        }
      } catch {}
    }

    async function loadMeta() {
      try {
        const [skillsRes, toolsetsRes, mcpsRes, configRes] = await Promise.allSettled([
          jarvisAPI.getHermesSkills(),
          jarvisAPI.getHermesToolsets(),
          jarvisAPI.getHermesMCPs(),
          jarvisAPI.getConfig(),
        ]);
        if (active) {
          if (skillsRes.status === "fulfilled" && skillsRes.value?.skills?.length > 0) {
            setSkills(skillsRes.value.skills);
          }
          if (toolsetsRes.status === "fulfilled" && toolsetsRes.value?.enabled?.length > 0) {
            setToolsets(toolsetsRes.value.enabled);
            setCfgEnabledToolsets(toolsetsRes.value.enabled);
          }
          if (mcpsRes.status === "fulfilled" && mcpsRes.value?.mcps) {
            setMcps(mcpsRes.value.mcps);
          }
          if (configRes.status === "fulfilled" && configRes.value) {
            const c = configRes.value;
            if (c.MODEL_BRAIN_FAST) setCfgFastBrain(c.MODEL_BRAIN_FAST);
            if (c.MODEL_BRAIN) setCfgSlowBrain(c.MODEL_BRAIN);
            if (c.FAST_BRAIN_TIMEOUT_SECONDS) setCfgTimeout(Number(c.FAST_BRAIN_TIMEOUT_SECONDS) || 60);
          }
        }
      } catch {}
    }

    syncData();
    loadMeta();
    const interval = setInterval(syncData, 3500);

    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  const handleManualRefresh = async () => {
    setIsRefreshing(true);
    try {
      const [tasksRes, autoRes] = await Promise.all([
        jarvisAPI.getHermesTasks(),
        jarvisAPI.getAutonomyStatus(),
      ]);
      setTasks(tasksRes);
      setAutonomyStatus(autoRes);
    } catch {}
    setIsRefreshing(false);
  };

  const handleDispatch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!prompt.trim() || isDispatching) return;

    setIsDispatching(true);
    setDispatchStatus(null);
    try {
      const res = await jarvisAPI.dispatchHermesTask(prompt.trim(), selectedLane);
      setDispatchStatus(`Orden despachada con éxito (${res.lane || selectedLane}).`);
      setPrompt("");
      handleManualRefresh();
    } catch (err: any) {
      setDispatchStatus(`Error: ${err?.message || "No se pudo despachar la tarea"}`);
    } finally {
      setIsDispatching(false);
    }
  };

  const toggleToolset = (name: string) => {
    setCfgEnabledToolsets((prev) =>
      prev.includes(name) ? prev.filter((t) => t !== name) : [...prev, name]
    );
  };

  const handleSaveConfig = async () => {
    setIsSavingConfig(true);
    setConfigSaveMsg(null);
    try {
      const updates: Record<string, string> = {
        MODEL_BRAIN_FAST: cfgFastBrain,
        MODEL_BRAIN: cfgSlowBrain,
        FAST_BRAIN_TIMEOUT_SECONDS: String(cfgTimeout),
        HERMES_ENABLED_TOOLSETS: cfgEnabledToolsets.join(","),
      };
      if (cfgApiKey.trim()) {
        updates.GEMINI_API_KEY = cfgApiKey.trim();
      }
      await jarvisAPI.updateConfig(updates);
      setConfigSaveMsg("✓ Configuración de Hermes guardada y aplicada con éxito.");
      setCfgApiKey("");
    } catch (e: any) {
      setConfigSaveMsg(`Error al guardar: ${e?.message || "Fallo de conexión"}`);
    } finally {
      setIsSavingConfig(false);
    }
  };

  const allTasks: TaskItem[] = [
    ...tasks.running_slow,
    ...tasks.running_fast,
    ...tasks.pending_slow,
    ...tasks.recent,
  ];

  const filteredTasks = allTasks.filter((t) => {
    if (taskFilter === "running") return t.state === "running" || t.state === "pending";
    if (taskFilter === "completed") return t.state === "completed" || t.state === "finished";
    return true;
  });

  const battery = autonomyStatus.sentinel?.battery;
  const isRunningAny = tasks.running_slow.length > 0 || tasks.running_fast.length > 0;

  return (
    <div
      className="fixed inset-0 w-screen h-screen flex flex-col z-40 select-none text-[#afaeac] font-sans overflow-hidden"
      style={{ backgroundColor: "#0c0c0e" }}
    >
      {/* ── BARRA SUPERIOR (HEADER INTEGRADO) ── */}
      <header className="h-14 border-b border-white/[0.08] px-6 flex items-center justify-between bg-[#121214]/90 backdrop-blur-md shrink-0">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2.5">
            <span
              className={`w-2.5 h-2.5 rounded-full ${
                isRunningAny ? "bg-purple-400 animate-pulse" : "bg-emerald-400"
              }`}
            />
            <h1 className="text-xs font-semibold tracking-[2px] text-[#faf9f6] uppercase font-mono">
              Hermes Agent Cockpit
            </h1>
          </div>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-500/10 border border-purple-500/20 text-purple-300">
            Nous AI Core v2
          </span>
        </div>

        {/* Pestañas de Navegación del Cockpit */}
        <div className="flex items-center gap-1 bg-[#161619] p-1 rounded-xl border border-white/[0.06]">
          {[
            { key: "chat", label: "Consola & Chat" },
            { key: "tasks", label: `Ledger (${allTasks.length})` },
            { key: "skills", label: `Skills (${skills.length})` },
            { key: "mcps", label: "Toolsets & MCPs" },
            { key: "autonomy", label: "Autonomía" },
            { key: "settings", label: "Ajustes" },
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key as HermesTab)}
              className={`px-3 py-1.5 rounded-lg text-xs font-mono transition cursor-pointer ${
                activeTab === tab.key
                  ? "bg-purple-500/20 text-purple-200 border border-purple-500/30 font-medium"
                  : "text-[#868584] hover:text-[#faf9f6] hover:bg-white/[0.03]"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Acciones Rápidas y Retorno */}
        <div className="flex items-center gap-3">
          {battery && (
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-[#161618] border border-white/[0.06] text-xs font-mono">
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  battery.percent <= 20
                    ? "bg-rose-500 animate-ping"
                    : battery.percent <= 35
                    ? "bg-amber-400"
                    : "bg-emerald-400"
                }`}
              />
              <span className="text-[#faf9f6]">{battery.percent}%</span>
              <span className="text-[#868584] text-[10px]">
                {battery.power_plugged ? "AC" : "BAT"}
              </span>
            </div>
          )}

          <button
            onClick={() => setActiveView("panel")}
            className="px-3 py-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-xs font-mono text-[#faf9f6] transition cursor-pointer"
            title="Abrir Panel de Control (Ctrl+2)"
          >
            Control Panel
          </button>

          <button
            onClick={() => setActiveView("orb")}
            className="px-3 py-1.5 rounded-lg bg-purple-500/15 hover:bg-purple-500/25 border border-purple-500/30 text-xs font-mono text-purple-200 transition cursor-pointer flex items-center gap-1"
            title="Volver al Orbe (Escape o Ctrl+1)"
          >
            <span>Orbe</span>
            <span className="text-[10px]">✕</span>
          </button>
        </div>
      </header>

      {/* ── CONTENIDO PRINCIPAL SEGÚN PESTAÑA ACTIVA ── */}
      <div className="flex-1 overflow-hidden p-6 flex flex-col">
        {/* 1. PESTAÑA CHAT & CONSOLA */}
        {activeTab === "chat" && (
          <div className="flex-1 flex gap-6 overflow-hidden">
            {/* Columna Izquierda: Despachador de Tareas */}
            <div className="w-[440px] flex flex-col gap-4 shrink-0 bg-[#121214] border border-white/[0.08] rounded-2xl p-5 shadow-xl">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono tracking-widest text-[#868584] uppercase">
                  Despachador Directo
                </span>
                <span className="text-[10px] font-mono text-purple-400">Ctrl + Enter</span>
              </div>

              {/* Selector de Carril */}
              <div className="grid grid-cols-2 gap-2.5">
                <button
                  type="button"
                  onClick={() => setSelectedLane("slow")}
                  className={`p-3 rounded-xl border text-left transition cursor-pointer flex flex-col ${
                    selectedLane === "slow"
                      ? "bg-purple-500/15 border-purple-500/40 text-[#faf9f6]"
                      : "bg-[#161618] border-white/[0.04] text-[#868584] hover:border-white/[0.1]"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold font-mono">SLOW_HERMES</span>
                    <span className="w-1.5 h-1.5 rounded-full bg-purple-400" />
                  </div>
                  <span className="text-[10px] opacity-80 mt-1">Multi-Herramientas & Terminal</span>
                </button>

                <button
                  type="button"
                  onClick={() => setSelectedLane("fast")}
                  className={`p-3 rounded-xl border text-left transition cursor-pointer flex flex-col ${
                    selectedLane === "fast"
                      ? "bg-cyan-500/15 border-cyan-500/40 text-[#faf9f6]"
                      : "bg-[#161618] border-white/[0.04] text-[#868584] hover:border-white/[0.1]"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold font-mono">FAST_HERMES</span>
                    <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
                  </div>
                  <span className="text-[10px] opacity-80 mt-1">Búsqueda Web Ultra-Rápida</span>
                </button>
              </div>

              {/* Textarea del Composer */}
              <div className="flex-1 flex flex-col gap-2">
                <textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
                      handleDispatch();
                    }
                  }}
                  rows={6}
                  placeholder={
                    selectedLane === "slow"
                      ? "Escribe cualquier orden autónoma para Hermes (ej. 'Crea un script en Blender que genere un fractal y guárdalo', 'Investiga el mercado y escribe un reporte')..."
                      : "Escribe una consulta rápida (ej. '¿Cuál es la cotización actual de Solana?', 'Busca las noticias del día')..."
                  }
                  className="w-full flex-1 bg-[#161618] border border-white/[0.08] focus:border-purple-500/50 rounded-xl p-3 text-xs text-[#faf9f6] placeholder-[#868584]/60 resize-none outline-none transition font-sans leading-relaxed"
                />
                <div className="flex items-center justify-between text-[10px] font-mono text-[#868584]">
                  <span>{prompt.length} caracteres</span>
                  <span>Presiona Ctrl+Enter para despachar</span>
                </div>
              </div>

              {/* Botón de Envío */}
              <button
                onClick={() => handleDispatch()}
                disabled={!prompt.trim() || isDispatching}
                className={`w-full py-3 rounded-xl font-medium text-xs tracking-wider uppercase transition flex items-center justify-center gap-2 cursor-pointer font-mono ${
                  !prompt.trim() || isDispatching
                    ? "bg-white/[0.04] text-[#868584] cursor-not-allowed"
                    : selectedLane === "slow"
                    ? "bg-purple-600 hover:bg-purple-500 text-white shadow-lg shadow-purple-900/30"
                    : "bg-cyan-600 hover:bg-cyan-500 text-white shadow-lg shadow-cyan-900/30"
                }`}
              >
                {isDispatching ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    <span>Ejecutando en Hermes...</span>
                  </>
                ) : (
                  <span>Despachar Orden</span>
                )}
              </button>

              {dispatchStatus && (
                <div
                  className={`p-2.5 rounded-lg text-xs font-mono ${
                    dispatchStatus.startsWith("Error")
                      ? "bg-rose-500/10 border border-rose-500/20 text-rose-300"
                      : "bg-emerald-500/10 border border-emerald-500/20 text-emerald-300"
                  }`}
                >
                  {dispatchStatus}
                </div>
              )}
            </div>

            {/* Columna Derecha: Stream de Respuestas y Conversaciones */}
            <div className="flex-1 bg-[#121214] border border-white/[0.08] rounded-2xl flex flex-col shadow-xl overflow-hidden">
              <div className="h-12 border-b border-white/[0.08] px-5 flex items-center justify-between bg-[#161618]/50 shrink-0">
                <span className="text-xs font-mono tracking-wider text-[#faf9f6] uppercase font-semibold">
                  Historial de Respuestas & Despachos
                </span>
                <span className="text-[11px] font-mono text-[#868584]">
                  {tasks.recent.length} registros recientes
                </span>
              </div>

              <div className="flex-1 overflow-y-auto p-5 flex flex-col gap-4">
                {tasks.recent.length === 0 ? (
                  <div className="flex-1 flex flex-col items-center justify-center text-center p-8 text-[#868584]">
                    <p className="text-xs font-mono">Sin órdenes registradas en esta sesión.</p>
                    <p className="text-[11px] text-[#868584]/60 mt-1">
                      Usa el panel de la izquierda o dicta por voz a JARVIS.
                    </p>
                  </div>
                ) : (
                  tasks.recent.map((t) => (
                    <div
                      key={t.task_id}
                      className="bg-[#161618] border border-white/[0.06] rounded-xl p-4 flex flex-col gap-2.5"
                    >
                      <div className="flex items-center justify-between text-[11px] font-mono">
                        <span className="px-2 py-0.5 rounded bg-purple-500/15 text-purple-300 font-semibold uppercase">
                          {t.lane || "hermes"}
                        </span>
                        <span className="text-[#868584]">{t.task_id?.slice(0, 8)}</span>
                      </div>
                      <div className="text-xs text-[#faf9f6] font-medium leading-relaxed bg-[#1c1c20] p-3 rounded-lg border border-white/[0.04]">
                        {t.prompt}
                      </div>
                      {t.result && (
                        <div className="text-xs text-[#e4e4e7] whitespace-pre-wrap font-mono bg-[#0c0c0e] p-3 rounded-lg border border-white/[0.06] leading-relaxed max-h-64 overflow-y-auto">
                          {t.result}
                        </div>
                      )}
                      {t.error && (
                        <div className="text-xs text-rose-300 font-mono bg-rose-950/20 p-3 rounded-lg border border-rose-500/20">
                          {t.error}
                        </div>
                      )}
                    </div>
                  ))
                )}
                <div ref={chatEndRef} />
              </div>
            </div>
          </div>
        )}

        {/* 2. PESTAÑA TASK LEDGER */}
        {activeTab === "tasks" && (
          <div className="flex-1 bg-[#121214] border border-white/[0.08] rounded-2xl flex flex-col shadow-xl overflow-hidden">
            <div className="h-12 border-b border-white/[0.08] px-5 flex items-center justify-between shrink-0 bg-[#161618]/50">
              <div className="flex items-center gap-3">
                <span className="text-xs font-mono tracking-wider text-[#faf9f6] uppercase font-semibold">
                  Task Ledger en Vivo
                </span>
                <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-white/[0.05] text-[#868584]">
                  {filteredTasks.length} tareas
                </span>
              </div>

              <div className="flex items-center gap-2">
                <div className="flex items-center bg-[#121214] rounded-lg p-0.5 border border-white/[0.06]">
                  {(["all", "running", "completed"] as const).map((f) => (
                    <button
                      key={f}
                      onClick={() => setTaskFilter(f)}
                      className={`px-2.5 py-1 rounded-md text-[11px] font-mono capitalize transition cursor-pointer ${
                        taskFilter === f
                          ? "bg-white/[0.1] text-[#faf9f6] font-medium"
                          : "text-[#868584] hover:text-[#faf9f6]"
                      }`}
                    >
                      {f === "all" ? "Todas" : f === "running" ? "En Marcha" : "Completadas"}
                    </button>
                  ))}
                </div>

                <button
                  onClick={handleManualRefresh}
                  className="p-1.5 rounded-lg bg-white/[0.05] hover:bg-white/[0.1] text-[#868584] hover:text-[#faf9f6] transition cursor-pointer"
                  title="Actualizar listado"
                >
                  <span className={`inline-block text-xs ${isRefreshing ? "animate-spin" : ""}`}>
                    ↻
                  </span>
                </button>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-5 flex flex-col gap-3">
              {filteredTasks.length === 0 ? (
                <div className="flex-1 flex flex-col items-center justify-center text-center p-8 text-[#868584]">
                  <p className="text-xs font-mono">No hay tareas que coincidan con este filtro.</p>
                </div>
              ) : (
                filteredTasks.map((task) => {
                  const isExpanded = expandedTaskId === task.task_id;
                  const isSlow = task.lane?.includes("slow");
                  const isRunning = task.state === "running" || task.state === "pending";

                  return (
                    <div
                      key={task.task_id}
                      className="bg-[#161618] border border-white/[0.06] rounded-xl p-4 transition hover:border-white/[0.12] flex flex-col gap-2.5"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase font-semibold ${
                              isSlow
                                ? "bg-purple-500/15 border border-purple-500/30 text-purple-300"
                                : "bg-cyan-500/15 border border-cyan-500/30 text-cyan-300"
                            }`}
                          >
                            {task.lane || "hermes"}
                          </span>

                          <span
                            className={`flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono uppercase ${
                              task.state === "completed" || task.state === "finished"
                                ? "bg-emerald-500/15 border border-emerald-500/30 text-emerald-300"
                                : task.state === "running"
                                ? "bg-blue-500/15 border border-blue-500/30 text-blue-300 animate-pulse"
                                : task.state === "failed"
                                ? "bg-rose-500/15 border border-rose-500/30 text-rose-300"
                                : "bg-amber-500/15 border border-amber-500/30 text-amber-300"
                            }`}
                          >
                            {isRunning && (
                              <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-ping" />
                            )}
                            <span>{task.state}</span>
                          </span>
                        </div>

                        <div className="flex items-center gap-2 text-[10px] font-mono text-[#868584]">
                          {task.duration && (
                            <span className="text-[#faf9f6]">{task.duration}s</span>
                          )}
                          <span>{task.task_id?.slice(0, 8)}</span>
                        </div>
                      </div>

                      <div className="text-xs text-[#faf9f6] font-medium leading-relaxed">
                        {task.prompt}
                      </div>

                      {(task.result || task.error) && (
                        <div className="mt-1">
                          <button
                            type="button"
                            onClick={() =>
                              setExpandedTaskId(isExpanded ? null : task.task_id)
                            }
                            className="text-[11px] font-mono text-purple-400 hover:text-purple-300 transition flex items-center gap-1 cursor-pointer"
                          >
                            <span>{isExpanded ? "Ocultar detalles" : "Ver detalles y salida"}</span>
                            <span className="text-[9px]">{isExpanded ? "▲" : "▼"}</span>
                          </button>

                          {isExpanded && (
                            <div className="mt-2 p-3 rounded-lg bg-[#0c0c0e] border border-white/[0.08] text-[11px] font-mono text-[#afaeac] whitespace-pre-wrap max-h-56 overflow-y-auto leading-relaxed">
                              {task.result && <div>{task.result}</div>}
                              {task.error && (
                                <div className="text-rose-400 mt-1">Error: {task.error}</div>
                              )}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </div>
        )}

        {/* 3. PESTAÑA SKILLS EXPLORER */}
        {activeTab === "skills" && (
          <div className="flex-1 bg-[#121214] border border-white/[0.08] rounded-2xl flex flex-col shadow-xl overflow-hidden">
            <div className="h-12 border-b border-white/[0.08] px-5 flex items-center justify-between shrink-0 bg-[#161618]/50">
              <span className="text-xs font-mono tracking-wider text-[#faf9f6] uppercase font-semibold">
                Skills Nativas Instaladas ({skills.length})
              </span>
              <span className="text-[11px] font-mono text-[#868584]">
                Ubicación: Hermes-Agent/skills
              </span>
            </div>

            <div className="flex-1 overflow-y-auto p-5 grid grid-cols-3 gap-4">
              {skills.map((s) => (
                <div
                  key={s.name}
                  className="bg-[#161618] border border-white/[0.06] hover:border-purple-500/30 rounded-xl p-4 flex flex-col justify-between gap-3 transition group"
                >
                  <div className="flex flex-col gap-1.5">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold font-mono text-purple-300 uppercase tracking-wide group-hover:text-purple-200">
                        {s.name}
                      </span>
                      <span className="w-1.5 h-1.5 rounded-full bg-purple-400 opacity-60 group-hover:opacity-100" />
                    </div>
                    <p className="text-xs text-[#868584] leading-relaxed">
                      {s.description}
                    </p>
                  </div>
                  <div className="pt-2 border-t border-white/[0.04] flex items-center justify-between text-[10px] font-mono text-[#868584]">
                    <span>STATUS: ACTIVO</span>
                    <span className="text-purple-400/80">CORE SKILL</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 4. PESTAÑA TOOLSETS & MCPS */}
        {activeTab === "mcps" && (
          <div className="flex-1 flex gap-6 overflow-hidden">
            {/* Toolsets */}
            <div className="flex-1 bg-[#121214] border border-white/[0.08] rounded-2xl flex flex-col shadow-xl overflow-hidden">
              <div className="h-12 border-b border-white/[0.08] px-5 flex items-center justify-between shrink-0 bg-[#161618]/50">
                <span className="text-xs font-mono tracking-wider text-[#faf9f6] uppercase font-semibold">
                  Toolsets del Agente ({toolsets.length})
                </span>
                <span className="text-[11px] font-mono text-emerald-400">100% OPERATIVOS</span>
              </div>
              <div className="flex-1 overflow-y-auto p-5 grid grid-cols-2 gap-3">
                {toolsets.map((t) => (
                  <div
                    key={t}
                    className="bg-[#161618] border border-white/[0.05] rounded-xl p-3 flex items-center justify-between"
                  >
                    <span className="text-xs font-mono font-medium text-[#faf9f6]">{t}</span>
                    <span className="w-2 h-2 rounded-full bg-emerald-400" />
                  </div>
                ))}
              </div>
            </div>

            {/* Servidores MCP */}
            <div className="w-[380px] bg-[#121214] border border-white/[0.08] rounded-2xl flex flex-col shadow-xl overflow-hidden shrink-0">
              <div className="h-12 border-b border-white/[0.08] px-5 flex items-center justify-between shrink-0 bg-[#161618]/50">
                <span className="text-xs font-mono tracking-wider text-[#faf9f6] uppercase font-semibold">
                  Servidores MCP
                </span>
                <span className="text-[11px] font-mono text-[#868584]">Model Context Protocol</span>
              </div>
              <div className="flex-1 overflow-y-auto p-5 flex flex-col gap-3">
                {mcps.length === 0 ? (
                  <div className="flex-1 flex flex-col items-center justify-center text-center p-6 text-[#868584]">
                    <p className="text-xs font-mono">Sin servidores MCP externos configurados.</p>
                    <p className="text-[11px] text-[#868584]/60 mt-1">
                      Puedes añadir servidores en ~/.hermes/config.yaml
                    </p>
                  </div>
                ) : (
                  mcps.map((m) => (
                    <div
                      key={m.name}
                      className="bg-[#161618] border border-white/[0.06] rounded-xl p-3 flex flex-col gap-1"
                    >
                      <span className="text-xs font-mono font-bold text-[#faf9f6]">{m.name}</span>
                      {m.command && (
                        <span className="text-[10px] font-mono text-[#868584] truncate">
                          {m.command}
                        </span>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        )}

        {/* 5. PESTAÑA AUTONOMÍA & SENTINEL */}
        {activeTab === "autonomy" && (
          <div className="flex-1 grid grid-cols-2 gap-6 overflow-hidden">
            {/* Centinela */}
            <div className="bg-[#121214] border border-white/[0.08] rounded-2xl flex flex-col shadow-xl p-6 gap-5">
              <div className="flex items-center justify-between pb-4 border-b border-white/[0.06]">
                <span className="text-xs font-mono font-bold tracking-wider text-[#faf9f6] uppercase">
                  System Sentinel (Proactivo)
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
                  ACTIVO (15s)
                </span>
              </div>

              <div className="flex flex-col gap-4">
                <div className="flex items-center justify-between py-2 border-b border-white/[0.04]">
                  <span className="text-xs font-mono text-[#868584]">Nivel de Batería</span>
                  <span className="text-xs font-mono text-[#faf9f6]">
                    {battery ? `${battery.percent}%` : "No disponible"}
                  </span>
                </div>
                <div className="flex items-center justify-between py-2 border-b border-white/[0.04]">
                  <span className="text-xs font-mono text-[#868584]">Alimentación Eléctrica</span>
                  <span className="text-xs font-mono text-[#faf9f6]">
                    {battery ? (battery.power_plugged ? "Conectado a CA" : "Batería / Descargando") : "—"}
                  </span>
                </div>
                <div className="flex items-center justify-between py-2 border-b border-white/[0.04]">
                  <span className="text-xs font-mono text-[#868584]">Alertas por Voz</span>
                  <span className="text-xs font-mono text-emerald-400">Proactivas (20% y 10%)</span>
                </div>
              </div>
            </div>

            {/* Cron Scheduler */}
            <div className="bg-[#121214] border border-white/[0.08] rounded-2xl flex flex-col shadow-xl p-6 gap-5">
              <div className="flex items-center justify-between pb-4 border-b border-white/[0.06]">
                <span className="text-xs font-mono font-bold tracking-wider text-[#faf9f6] uppercase">
                  Hermes Autonomous Scheduler
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
                  CRON ACTIVO (60s)
                </span>
              </div>

              <div className="flex flex-col gap-4">
                <div className="flex items-center justify-between py-2 border-b border-white/[0.04]">
                  <span className="text-xs font-mono text-[#868584]">Intervalo de Evaluación</span>
                  <span className="text-xs font-mono text-[#faf9f6]">Cada 60 segundos</span>
                </div>
                <div className="flex items-center justify-between py-2 border-b border-white/[0.04]">
                  <span className="text-xs font-mono text-[#868584]">Routinas de Auto-Aprendizaje</span>
                  <span className="text-xs font-mono text-[#faf9f6]">Memory Consolidator pasivo</span>
                </div>
                <div className="flex items-center justify-between py-2 border-b border-white/[0.04]">
                  <span className="text-xs font-mono text-[#868584]">Total Jobs Ejecutados</span>
                  <span className="text-xs font-mono text-[#faf9f6]">
                    {autonomyStatus.scheduler?.total_jobs_executed ?? 0}
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 6. PESTAÑA AJUSTES / CONFIGURACIÓN */}
        {activeTab === "settings" && (
          <div className="flex-1 flex gap-6 overflow-hidden">
            {/* Columna Izquierda: Modelos y Timeouts */}
            <div className="w-[460px] bg-[#121214] border border-white/[0.08] rounded-2xl flex flex-col shadow-xl p-6 gap-5 overflow-y-auto shrink-0">
              <div className="flex items-center justify-between pb-3 border-b border-white/[0.06]">
                <span className="text-xs font-mono font-bold tracking-wider text-[#faf9f6] uppercase">
                  Cerebro de Hermes
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-500/10 text-purple-300 border border-purple-500/20">
                  LLM CONFIG
                </span>
              </div>

              {/* Fast Brain */}
              <div className="flex flex-col gap-1.5">
                <label className="text-[11px] font-mono text-[#868584] uppercase">
                  Fast Brain (Consultas y Web)
                </label>
                <input
                  type="text"
                  value={cfgFastBrain}
                  onChange={(e) => setCfgFastBrain(e.target.value)}
                  className="bg-[#161618] border border-white/[0.08] focus:border-purple-500/50 rounded-xl px-3 py-2 text-xs font-mono text-[#faf9f6] outline-none"
                  placeholder="gemini-2.5-flash"
                />
              </div>

              {/* Slow Brain */}
              <div className="flex flex-col gap-1.5">
                <label className="text-[11px] font-mono text-[#868584] uppercase">
                  Slow Brain (Razonamiento Profundo y Código)
                </label>
                <input
                  type="text"
                  value={cfgSlowBrain}
                  onChange={(e) => setCfgSlowBrain(e.target.value)}
                  className="bg-[#161618] border border-white/[0.08] focus:border-purple-500/50 rounded-xl px-3 py-2 text-xs font-mono text-[#faf9f6] outline-none"
                  placeholder="gemini-2.5-pro"
                />
              </div>

              {/* Timeout */}
              <div className="flex flex-col gap-1.5">
                <div className="flex items-center justify-between text-[11px] font-mono">
                  <span className="text-[#868584] uppercase">Timeout de Agente</span>
                  <span className="text-[#faf9f6]">{cfgTimeout} segundos</span>
                </div>
                <input
                  type="range"
                  min="15"
                  max="300"
                  step="5"
                  value={cfgTimeout}
                  onChange={(e) => setCfgTimeout(Number(e.target.value))}
                  className="w-full accent-purple-500 cursor-pointer"
                />
              </div>

              {/* API Key Pool */}
              <div className="pt-3 border-t border-white/[0.06] flex flex-col gap-2">
                <span className="text-[11px] font-mono text-[#868584] uppercase">
                  Añadir API Key de Gemini al Pool
                </span>
                <input
                  type="password"
                  value={cfgApiKey}
                  onChange={(e) => setCfgApiKey(e.target.value)}
                  placeholder="AIzaSy... (opcional para rotar o actualizar)"
                  className="bg-[#161618] border border-white/[0.08] focus:border-purple-500/50 rounded-xl px-3 py-2 text-xs font-mono text-[#faf9f6] outline-none"
                />
              </div>

              {/* Botón Guardar */}
              <div className="mt-auto pt-4 border-t border-white/[0.06] flex flex-col gap-3">
                <button
                  onClick={handleSaveConfig}
                  disabled={isSavingConfig}
                  className="w-full py-3 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-mono font-medium text-xs tracking-wider uppercase transition shadow-lg shadow-purple-900/30 cursor-pointer disabled:opacity-50"
                >
                  {isSavingConfig ? "Guardando en .env..." : "Guardar Cambios"}
                </button>

                {configSaveMsg && (
                  <div
                    className={`p-2.5 rounded-lg text-xs font-mono ${
                      configSaveMsg.startsWith("Error")
                        ? "bg-rose-500/10 border border-rose-500/20 text-rose-300"
                        : "bg-emerald-500/10 border border-emerald-500/20 text-emerald-300"
                    }`}
                  >
                    {configSaveMsg}
                  </div>
                )}
              </div>
            </div>

            {/* Columna Derecha: Matriz de Toolsets (Activar/Desactivar) */}
            <div className="flex-1 bg-[#121214] border border-white/[0.08] rounded-2xl flex flex-col shadow-xl p-6 gap-5 overflow-y-auto">
              <div className="flex items-center justify-between pb-3 border-b border-white/[0.06]">
                <span className="text-xs font-mono font-bold tracking-wider text-[#faf9f6] uppercase">
                  Capacidades & Toolsets Habilitados ({cfgEnabledToolsets.length} / {ALL_POSSIBLE_TOOLSETS.length})
                </span>
                <span className="text-[11px] font-mono text-[#868584]">
                  Haz clic para activar o desactivar
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3">
                {ALL_POSSIBLE_TOOLSETS.map((t) => {
                  const isEnabled = cfgEnabledToolsets.includes(t);
                  return (
                    <button
                      key={t}
                      type="button"
                      onClick={() => toggleToolset(t)}
                      className={`p-3.5 rounded-xl border text-left transition flex items-center justify-between cursor-pointer ${
                        isEnabled
                          ? "bg-purple-500/10 border-purple-500/30 hover:border-purple-500/50"
                          : "bg-[#161618] border-white/[0.04] opacity-50 hover:opacity-75"
                      }`}
                    >
                      <div className="flex flex-col gap-0.5">
                        <span className="text-xs font-mono font-bold text-[#faf9f6] uppercase">
                          {t}
                        </span>
                        <span className="text-[10px] font-mono text-[#868584]">
                          {isEnabled ? "HABILITADO" : "DESHABILITADO"}
                        </span>
                      </div>

                      <div
                        className={`w-9 h-5 rounded-full p-0.5 transition-colors duration-200 ease-in-out ${
                          isEnabled ? "bg-purple-500" : "bg-white/[0.1]"
                        }`}
                      >
                        <div
                          className={`w-4 h-4 rounded-full bg-white transition-transform duration-200 ease-in-out ${
                            isEnabled ? "translate-x-4" : "translate-x-0"
                          }`}
                        />
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
