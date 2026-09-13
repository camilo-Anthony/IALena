import React, { useEffect, useState, useRef } from "react";
import { jarvisAPI } from "../../hooks/useJarvisAPI";
import type { HermesCronJob, HermesCronOutput, HermesMemoryPayload, TaskItem } from "../../types";

type HermesSubTab = "chat" | "tasks" | "skills" | "memory" | "mcps" | "cron" | "autonomy" | "settings";

interface SkillInfo {
  name: string;
  description: string;
  source: string;
  writable: boolean;
  path: string;
}

const ALL_POSSIBLE_TOOLSETS = [
  "web", "file", "terminal", "browser", "skills", "todo", "memory",
  "code_execution", "delegation", "cronjob", "vision", "image_gen", "tts", "computer_use"
];

interface RuntimeCapabilities {
  registry?: {
    slow_toolsets?: string[];
    slow_mcp_status?: "unconfigured" | "initializing" | "ready" | "failed";
    slow_mcp_servers?: string[];
    slow_mcp_error?: string;
  };
  active_capabilities?: string[];
}

export interface HermesCockpitTabProps {
  subTab?: HermesSubTab;
  hideHeaderBar?: boolean;
}

export function HermesCockpitTab({ subTab, hideHeaderBar = false }: HermesCockpitTabProps) {
  const [internalSubTab, setInternalSubTab] = useState<HermesSubTab>("chat");
  const activeSubTab = subTab || internalSubTab;

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
  const [skills, setSkills] = useState<SkillInfo[]>([]);
  const [toolsets, setToolsets] = useState<string[]>([]);
  const [runtimeCapabilities, setRuntimeCapabilities] = useState<RuntimeCapabilities>({});
  const [mcps, setMcps] = useState<
    Array<{
      name: string;
      command?: string;
      args?: string[];
      url?: string;
      enabled?: boolean;
    }>
  >([]);
  const [isAddingMcp, setIsAddingMcp] = useState(false);
  const [newMcpName, setNewMcpName] = useState("");
  const [newMcpCommand, setNewMcpCommand] = useState("");
  const [newMcpArgs, setNewMcpArgs] = useState("");
  const [newMcpUrl, setNewMcpUrl] = useState("");
  const [mcpActionMsg, setMcpActionMsg] = useState<string | null>(null);

  // Estado de memoria y automatizaciones nativas de Hermes.
  const [memory, setMemory] = useState<HermesMemoryPayload | null>(null);
  const [memoryError, setMemoryError] = useState<string | null>(null);
  const [memoryRequest, setMemoryRequest] = useState("");
  const [memoryRequestKind, setMemoryRequestKind] = useState<"remember" | "forget">("remember");
  const [memoryRequestStatus, setMemoryRequestStatus] = useState<string | null>(null);
  const [isSubmittingMemoryRequest, setIsSubmittingMemoryRequest] = useState(false);
  const [cronJobs, setCronJobs] = useState<HermesCronJob[]>([]);
  const [cronError, setCronError] = useState<string | null>(null);
  const [cronStatus, setCronStatus] = useState<string | null>(null);
  const [cronName, setCronName] = useState("");
  const [cronSchedule, setCronSchedule] = useState("");
  const [cronPrompt, setCronPrompt] = useState("");
  const [isSavingCron, setIsSavingCron] = useState(false);
  const [editingCronId, setEditingCronId] = useState<string | null>(null);
  const [editCronName, setEditCronName] = useState("");
  const [editCronSchedule, setEditCronSchedule] = useState("");
  const [editCronPrompt, setEditCronPrompt] = useState("");
  const [isReloadingSlow, setIsReloadingSlow] = useState(false);
  const [reloadSlowStatus, setReloadSlowStatus] = useState<string | null>(null);
  const [cronOutputs, setCronOutputs] = useState<Record<string, HermesCronOutput[]>>({});
  const [loadingCronOutputId, setLoadingCronOutputId] = useState<string | null>(null);

  // Estados de Ajustes Operativos de Hermes
  const [cfgMemoryEnabled, setCfgMemoryEnabled] = useState(true);
  const [cfgSoulEnabled, setCfgSoulEnabled] = useState(true);
  const [cfgStrictGate, setCfgStrictGate] = useState(true);
  const [cfgTimeout, setCfgTimeout] = useState(360);
  const [cfgEnabledToolsets, setCfgEnabledToolsets] = useState<string[]>(ALL_POSSIBLE_TOOLSETS);
  const [cfgApiKey, setCfgApiKey] = useState("");
  const [keyPoolCount, setKeyPoolCount] = useState(4);
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
  const mcpStatus = runtimeCapabilities.registry?.slow_mcp_status ?? "unconfigured";
  const mcpStatusLabel = {
    unconfigured: "SIN CONFIGURAR",
    initializing: "INICIALIZANDO",
    ready: "OPERATIVO",
    failed: "FALLÓ",
  }[mcpStatus];
  const mcpStatusClass = {
    unconfigured: "text-[#868584]",
    initializing: "text-amber-300",
    ready: "text-emerald-400",
    failed: "text-red-300",
  }[mcpStatus];

  useEffect(() => {
    let active = true;

    async function syncData() {
      try {
        const [tasksRes, autoRes, capabilitiesRes] = await Promise.all([
          jarvisAPI.getHermesTasks(),
          jarvisAPI.getAutonomyStatus(),
          jarvisAPI.getCapabilities(),
        ]);
        if (active) {
          setTasks(tasksRes);
          setAutonomyStatus(autoRes);
          setRuntimeCapabilities(capabilitiesRes as RuntimeCapabilities);
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
          if (toolsetsRes.status === "fulfilled") {
            const enabled = toolsetsRes.value?.enabled || [];
            setToolsets(enabled);
            setCfgEnabledToolsets(enabled);
          }
          if (mcpsRes.status === "fulfilled" && mcpsRes.value?.mcps) {
            setMcps(mcpsRes.value.mcps);
          }
          if (configRes.status === "fulfilled" && configRes.value) {
            const c = configRes.value;
            if (c.HERMES_SKIP_MEMORY !== undefined) {
              setCfgMemoryEnabled(c.HERMES_SKIP_MEMORY !== "1");
            }
            if (c.HERMES_LOAD_SOUL_IDENTITY !== undefined) {
              setCfgSoulEnabled(c.HERMES_LOAD_SOUL_IDENTITY !== "0");
            }
            if (c.STRICT_HERMES_INTENT_GATE !== undefined) {
              setCfgStrictGate(c.STRICT_HERMES_INTENT_GATE !== "0");
            }
            if (c.HERMES_SLOW_TIMEOUT_SECONDS) {
              setCfgTimeout(Number(c.HERMES_SLOW_TIMEOUT_SECONDS) || 360);
            } else if (c.FAST_BRAIN_TIMEOUT_SECONDS) {
              setCfgTimeout(Number(c.FAST_BRAIN_TIMEOUT_SECONDS) || 60);
            }
            const keysCount = Object.keys(c).filter((k) => k.startsWith("HERMES_API_KEY_")).length;
            if (keysCount > 0) setKeyPoolCount(keysCount);
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
      const [tasksRes, autoRes, capabilitiesRes] = await Promise.all([
        jarvisAPI.getHermesTasks(),
        jarvisAPI.getAutonomyStatus(),
        jarvisAPI.getCapabilities(),
      ]);
      setTasks(tasksRes);
      setAutonomyStatus(autoRes);
      setRuntimeCapabilities(capabilitiesRes as RuntimeCapabilities);
    } catch {}
    setIsRefreshing(false);
  };

  const refreshMemory = async () => {
    setMemoryError(null);
    try {
      setMemory(await jarvisAPI.getHermesMemory());
    } catch (error: any) {
      setMemoryError(error?.message || "No se pudo leer la memoria de Hermes.");
    }
  };

  const handleMemoryRequest = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!memoryRequest.trim() || isSubmittingMemoryRequest) return;
    if (memoryRequestKind === "forget" && !confirm("Hermes evaluará y eliminará sólo la memoria que coincida con esta solicitud. ¿Continuar?")) return;

    setIsSubmittingMemoryRequest(true);
    setMemoryRequestStatus(null);
    const instruction = memoryRequestKind === "remember"
      ? "Evalúa el dato, y si es útil y persistente, guárdalo con la herramienta de memoria de Hermes."
      : "Busca la memoria indicada y elimínala sólo si la coincidencia es inequívoca. No elimines información relacionada por inferencia.";
    try {
      const result = await jarvisAPI.dispatchHermesTask(
        `[SOLICITUD DE MEMORIA DESDE JARVIS]\n${instruction}\n\nSOLICITUD DEL USUARIO: ${memoryRequest.trim()}`,
        "slow",
      );
      setMemoryRequestStatus(`Solicitud enviada a Hermes (${result.call_id.slice(0, 8)}). Revisa el ledger para el resultado.`);
      setMemoryRequest("");
    } catch (error: any) {
      setMemoryRequestStatus(error?.message || "No se pudo enviar la solicitud de memoria.");
    } finally {
      setIsSubmittingMemoryRequest(false);
    }
  };

  const refreshCron = async () => {
    setCronError(null);
    try {
      const result = await jarvisAPI.getHermesCronJobs();
      setCronJobs(result.jobs || []);
      if (result.error) setCronError(result.error);
    } catch (error: any) {
      setCronError(error?.message || "No se pudieron leer las automatizaciones.");
    }
  };

  useEffect(() => {
    if (activeSubTab === "memory") void refreshMemory();
    if (activeSubTab === "cron") void refreshCron();
  }, [activeSubTab]);

  const handleCreateCron = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!cronPrompt.trim() || !cronSchedule.trim() || isSavingCron) return;
    setIsSavingCron(true);
    setCronStatus(null);
    setCronError(null);
    try {
      const result = await jarvisAPI.createHermesCronJob(
        cronPrompt.trim(),
        cronSchedule.trim(),
        cronName.trim(),
      );
      if (!result.success) throw new Error(result.error || "Hermes rechazó la automatización.");
      setCronName("");
      setCronSchedule("");
      setCronPrompt("");
      setCronStatus("Automatización creada en Hermes.");
      await refreshCron();
    } catch (error: any) {
      setCronError(error?.message || "No se pudo crear la automatización.");
    } finally {
      setIsSavingCron(false);
    }
  };

  const handleCronAction = async (jobId: string, action: "pause" | "resume" | "trigger") => {
    setCronStatus(null);
    setCronError(null);
    try {
      const result = await jarvisAPI.updateHermesCronJob(jobId, action);
      if (!result.success) throw new Error(result.error || "Hermes no pudo actualizar la automatización.");
      setCronStatus(
        action === "pause" ? "Automatización pausada." : action === "resume" ? "Automatización reanudada." : "Ejecución solicitada.",
      );
      await refreshCron();
    } catch (error: any) {
      setCronError(error?.message || "No se pudo actualizar la automatización.");
    }
  };

  const startEditingCron = (job: HermesCronJob) => {
    setEditingCronId(job.id);
    setEditCronName(job.name || "");
    setEditCronSchedule(job.schedule_display || "");
    setEditCronPrompt(job.prompt || "");
    setCronError(null);
    setCronStatus(null);
  };

  const handleSaveCronEdit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!editingCronId || !editCronPrompt.trim() || !editCronSchedule.trim()) return;
    setCronError(null);
    try {
      const result = await jarvisAPI.editHermesCronJob(editingCronId, {
        name: editCronName.trim(),
        schedule: editCronSchedule.trim(),
        prompt: editCronPrompt.trim(),
      });
      if (!result.success) throw new Error(result.error || "Hermes no pudo actualizar la automatización.");
      setEditingCronId(null);
      setCronStatus("Automatización actualizada.");
      await refreshCron();
    } catch (error: any) {
      setCronError(error?.message || "No se pudo actualizar la automatización.");
    }
  };

  const handleDeleteCron = async (job: HermesCronJob) => {
    if (!confirm(`¿Eliminar la automatización '${job.name || job.id}'? También se eliminará su salida histórica.`)) return;
    setCronError(null);
    try {
      const result = await jarvisAPI.deleteHermesCronJob(job.id);
      if (!result.success) throw new Error(result.error || "Hermes no pudo eliminar la automatización.");
      if (editingCronId === job.id) setEditingCronId(null);
      setCronStatus("Automatización eliminada.");
      await refreshCron();
    } catch (error: any) {
      setCronError(error?.message || "No se pudo eliminar la automatización.");
    }
  };

  const handleToggleCronOutputs = async (jobId: string) => {
    if (cronOutputs[jobId]) {
      setCronOutputs((current) => {
        const next = { ...current };
        delete next[jobId];
        return next;
      });
      return;
    }
    setLoadingCronOutputId(jobId);
    setCronError(null);
    try {
      const result = await jarvisAPI.getHermesCronOutputs(jobId);
      if (result.error) throw new Error(result.error);
      setCronOutputs((current) => ({ ...current, [jobId]: result.outputs || [] }));
    } catch (error: any) {
      setCronError(error?.message || "No se pudo leer el historial de la automatización.");
    } finally {
      setLoadingCronOutputId(null);
    }
  };

  const handleReloadSlow = async () => {
    if (isReloadingSlow || isRunningAny) return;
    setIsReloadingSlow(true);
    setReloadSlowStatus(null);
    try {
      const result = await jarvisAPI.reloadHermesSlow();
      if (!result.success) throw new Error(result.error || "Hermes SLOW rechazó la recarga.");
      setReloadSlowStatus(result.message || "Hermes SLOW recargado.");
      await handleManualRefresh();
    } catch (error: any) {
      setReloadSlowStatus(error?.message || "No se pudo recargar Hermes SLOW.");
    } finally {
      setIsReloadingSlow(false);
    }
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
        HERMES_SKIP_MEMORY: cfgMemoryEnabled ? "0" : "1",
        HERMES_LOAD_SOUL_IDENTITY: cfgSoulEnabled ? "1" : "0",
        STRICT_HERMES_INTENT_GATE: cfgStrictGate ? "1" : "0",
        HERMES_SLOW_TIMEOUT_SECONDS: String(cfgTimeout),
        HERMES_ENABLED_TOOLSETS: cfgEnabledToolsets.join(","),
      };
      if (cfgApiKey.trim()) {
        const nextIndex = keyPoolCount + 1;
        updates[`HERMES_API_KEY_${nextIndex}`] = cfgApiKey.trim();
      }
      await jarvisAPI.updateConfig(updates);
      setConfigSaveMsg("Ajustes guardados. Reinicia JARVIS para aplicarlos al worker Hermes activo.");
      if (cfgApiKey.trim()) {
        setKeyPoolCount((prev) => prev + 1);
        setCfgApiKey("");
      }
    } catch (e: any) {
      setConfigSaveMsg(`Error al guardar: ${e?.message || "Fallo de conexión"}`);
    } finally {
      setIsSavingConfig(false);
    }
  };

  const refreshMcps = async () => {
    try {
      const res = await jarvisAPI.getHermesMCPs();
      if (res?.mcps) setMcps(res.mcps);
    } catch {}
  };

  const handleToggleMcp = async (name: string) => {
    setMcpActionMsg(null);
    try {
      await jarvisAPI.toggleHermesMCP(name);
      await refreshMcps();
      setMcpActionMsg("Configuración actualizada. Reinicia JARVIS para registrar el cambio en Hermes.");
    } catch (e: any) {
      setMcpActionMsg(`Error: ${e?.message || "No se pudo alternar el servidor"}`);
    }
  };

  const handleDeleteMcp = async (name: string) => {
    if (!confirm(`¿Estás seguro de eliminar el servidor MCP '${name}' de config.yaml?`)) return;
    setMcpActionMsg(null);
    try {
      await jarvisAPI.deleteHermesMCP(name);
      await refreshMcps();
      setMcpActionMsg("Servidor eliminado de configuración. Reinicia JARVIS para descargarlo del worker Hermes.");
    } catch (e: any) {
      setMcpActionMsg(`Error: ${e?.message || "No se pudo eliminar el servidor"}`);
    }
  };

  const handleCreateMcp = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!newMcpName.trim()) return;
    setMcpActionMsg(null);
    try {
      const argsList = newMcpArgs.trim() ? newMcpArgs.trim().split(" ") : [];
      await jarvisAPI.saveHermesMCP({
        name: newMcpName.trim().toLowerCase(),
        command: newMcpCommand.trim() || undefined,
        args: argsList.length ? argsList : undefined,
        url: newMcpUrl.trim() || undefined,
        enabled: true,
      });
      setIsAddingMcp(false);
      setNewMcpName("");
      setNewMcpCommand("");
      setNewMcpArgs("");
      setNewMcpUrl("");
      await refreshMcps();
      setMcpActionMsg("Servidor guardado. Reinicia JARVIS para que Hermes intente registrarlo.");
    } catch (e: any) {
      setMcpActionMsg(`Error al guardar servidor MCP: ${e?.message || "Fallo de conexión"}`);
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
    <div className="flex-1 flex flex-col h-full overflow-hidden space-y-4">
      {/* ── Sub-barra de Navegación del Cockpit (solo si no está oculta) ── */}
      {!hideHeaderBar && (
        <div className="flex items-center justify-between bg-[#161619] p-2 rounded-2xl border border-white/[0.06] shrink-0">
          <div className="flex items-center gap-1">
            {[
              { key: "chat", label: "Consola & Chat" },
              { key: "tasks", label: `Ledger (${allTasks.length})` },
              { key: "skills", label: `Skills (${skills.length})` },
              { key: "memory", label: "Memoria" },
              { key: "mcps", label: `Toolsets (${toolsets.length})` },
              { key: "cron", label: `Cron (${cronJobs.length})` },
              { key: "autonomy", label: "Autonomía" },
              { key: "settings", label: "Ajustes de Hermes" },
            ].map((tab) => (
              <button
                key={tab.key}
                onClick={() => setInternalSubTab(tab.key as HermesSubTab)}
                className={`px-3.5 py-1.5 rounded-xl text-xs font-mono transition cursor-pointer ${
                  activeSubTab === tab.key
                    ? "bg-purple-500/20 text-purple-200 border border-purple-500/30 font-semibold"
                    : "text-[#868584] hover:text-[#faf9f6] hover:bg-white/[0.03]"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-3 pr-2">
            {battery && (
              <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-[#111113] border border-white/[0.06] text-xs font-mono">
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

            <span
              className={`w-2 h-2 rounded-full ${
                isRunningAny ? "bg-purple-400 animate-pulse" : "bg-emerald-400"
              }`}
              title={isRunningAny ? "Hermes ocupado en tarea" : "Hermes en espera"}
            />
          </div>
        </div>
      )}

      {/* ── Contenido de las Sub-pestañas ── */}
      <div className="flex-1 overflow-hidden flex flex-col min-h-0">
        {/* 1. CHAT & CONSOLA */}
        {activeSubTab === "chat" && (
          <div className="flex-1 flex gap-5 overflow-hidden min-h-0">
            {/* Despacho */}
            <div className="w-[420px] flex flex-col gap-3.5 shrink-0 bg-[#161618] border border-white/[0.08] rounded-2xl p-5 shadow-sm">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono tracking-widest text-[#868584] uppercase">
                  Despachador Directo
                </span>
                <span className="text-[10px] font-mono text-purple-400">Ctrl + Enter</span>
              </div>

              {/* Selector de Carril */}
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setSelectedLane("slow")}
                  className={`p-3 rounded-xl border text-left transition cursor-pointer flex flex-col ${
                    selectedLane === "slow"
                      ? "bg-purple-500/15 border-purple-500/40 text-[#faf9f6]"
                      : "bg-[#111113] border-white/[0.04] text-[#868584] hover:border-white/[0.1]"
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
                      : "bg-[#111113] border-white/[0.04] text-[#868584] hover:border-white/[0.1]"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold font-mono">FAST_HERMES</span>
                    <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
                  </div>
                  <span className="text-[10px] opacity-80 mt-1">Búsqueda Web Ultra-Rápida</span>
                </button>
              </div>

              {/* Composer */}
              <div className="flex-1 flex flex-col gap-2 min-h-0">
                <textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
                      handleDispatch();
                    }
                  }}
                  rows={5}
                  placeholder={
                    selectedLane === "slow"
                      ? "Escribe cualquier orden autónoma para Hermes (ej. 'Crea un script en Blender 5.1 que genere una mesa y ejecútalo', 'Investiga en la web y guarda un informe')..."
                      : "Escribe una consulta rápida (ej. '¿Cuál es el precio de Bitcoin?', 'Noticias de IA de hoy')..."
                  }
                  className="w-full flex-1 bg-[#111113] border border-white/[0.08] focus:border-purple-500/50 rounded-xl p-3 text-xs text-[#faf9f6] placeholder-[#868584]/60 resize-none outline-none transition font-sans leading-relaxed"
                />
                <div className="flex items-center justify-between text-[10px] font-mono text-[#868584]">
                  <span>{prompt.length} caracteres</span>
                  <span>Presiona Ctrl+Enter para despachar</span>
                </div>
              </div>

              {/* Botón Envío */}
              <button
                onClick={() => handleDispatch()}
                disabled={!prompt.trim() || isDispatching}
                className={`w-full py-2.5 rounded-xl font-medium text-xs tracking-wider uppercase transition flex items-center justify-center gap-2 cursor-pointer font-mono ${
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

            {/* Stream de Respuestas */}
            <div className="flex-1 bg-[#161618] border border-white/[0.08] rounded-2xl flex flex-col shadow-sm overflow-hidden min-h-0">
              <div className="h-11 border-b border-white/[0.08] px-5 flex items-center justify-between bg-[#111113]/50 shrink-0">
                <span className="text-xs font-mono tracking-wider text-[#faf9f6] uppercase font-semibold">
                  Historial de Respuestas & Despachos
                </span>
                <span className="text-[11px] font-mono text-[#868584]">
                  {tasks.recent.length} registros recientes
                </span>
              </div>

              <div className="flex-1 overflow-y-auto p-5 flex flex-col gap-4 min-h-0">
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
                      className="bg-[#111113] border border-white/[0.06] rounded-xl p-4 flex flex-col gap-2.5"
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

        {/* 2. TASK LEDGER */}
        {activeSubTab === "tasks" && (
          <div className="flex-1 bg-[#161618] border border-white/[0.08] rounded-2xl flex flex-col shadow-sm overflow-hidden min-h-0">
            <div className="h-11 border-b border-white/[0.08] px-5 flex items-center justify-between shrink-0 bg-[#111113]/50">
              <div className="flex items-center gap-3">
                <span className="text-xs font-mono tracking-wider text-[#faf9f6] uppercase font-semibold">
                  Task Ledger en Vivo
                </span>
                <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-white/[0.05] text-[#868584]">
                  {filteredTasks.length} tareas
                </span>
              </div>

              <div className="flex items-center gap-2">
                <div className="flex items-center bg-[#111113] rounded-lg p-0.5 border border-white/[0.06]">
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

            <div className="flex-1 overflow-y-auto p-5 flex flex-col gap-3 min-h-0">
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
                      className="bg-[#111113] border border-white/[0.06] rounded-xl p-4 transition hover:border-white/[0.12] flex flex-col gap-2.5"
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

        {/* 3. SKILLS EXPLORER */}
        {activeSubTab === "skills" && (
          <div className="flex-1 bg-[#161618] border border-white/[0.08] rounded-2xl flex flex-col shadow-sm overflow-hidden min-h-0">
            <div className="h-11 border-b border-white/[0.08] px-5 flex items-center justify-between shrink-0 bg-[#111113]/50">
              <span className="text-xs font-mono tracking-wider text-[#faf9f6] uppercase font-semibold">
                Skills Activas de Hermes ({skills.length})
              </span>
              <span className="text-[11px] font-mono text-[#868584]">
                Integradas, de perfil y externas
              </span>
            </div>

            <div className="flex-1 overflow-y-auto p-5 grid grid-cols-3 gap-3.5 min-h-0">
              {skills.map((s) => (
                <div
                  key={s.name}
                  className="bg-[#111113] border border-white/[0.06] hover:border-purple-500/30 rounded-xl p-4 flex flex-col justify-between gap-3 transition group"
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
                    <span>{s.writable ? "GESTIONADA POR HERMES" : "SOLO LECTURA"}</span>
                    <span className="text-purple-400/80 uppercase">{s.source}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 4. MEMORIA E IDENTIDAD */}
        {activeSubTab === "memory" && (
          <div className="flex-1 bg-[#161618] border border-white/[0.08] rounded-2xl flex flex-col shadow-sm overflow-hidden min-h-0">
            <div className="h-11 border-b border-white/[0.08] px-5 flex items-center justify-between shrink-0 bg-[#111113]/50">
              <div>
                <span className="text-xs font-mono tracking-wider text-[#faf9f6] uppercase font-semibold">
                  Memoria e identidad de Hermes
                </span>
                <span className="ml-3 text-[10px] font-mono text-[#868584]">
                  {memory?.home_ready ? "HERMES_HOME DISPONIBLE" : "HERMES_HOME NO DISPONIBLE"}
                </span>
              </div>
              <button
                type="button"
                onClick={refreshMemory}
                className="p-1.5 rounded-lg bg-white/[0.05] hover:bg-white/[0.1] text-[#868584] hover:text-[#faf9f6] transition cursor-pointer"
                title="Actualizar memoria"
              >
                ↻
              </button>
            </div>

            {memoryError && (
              <div className="mx-5 mt-4 p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-xs font-mono text-rose-200">
                {memoryError}
              </div>
            )}

            <div className="flex-1 overflow-y-auto px-5 py-4 min-h-0">
              <p className="text-xs text-[#868584] leading-relaxed max-w-3xl mb-5">
                JARVIS presenta el contexto persistente que Hermes controla. La escritura permanece en Hermes para conservar trazabilidad, consolidación y protección de la identidad.
              </p>

              {[
                { key: "identity", label: "SOUL.md", description: "Identidad, principios y directivas del agente." },
                { key: "user_memory", label: "USER.md", description: "Datos y preferencias persistentes del usuario." },
                { key: "agent_memory", label: "MEMORY.md", description: "Memoria operativa consolidada por Hermes." },
              ].map(({ key, label, description }) => {
                const document = memory?.[key as keyof Pick<HermesMemoryPayload, "identity" | "user_memory" | "agent_memory">];
                return (
                  <section key={key} className="py-4 border-t border-white/[0.07] first:border-t-0 first:pt-0">
                    <div className="flex items-start justify-between gap-4 mb-3">
                      <div>
                        <h3 className="text-xs font-mono font-semibold text-[#faf9f6]">{label}</h3>
                        <p className="mt-1 text-[11px] text-[#868584]">{description}</p>
                      </div>
                      <span className={`shrink-0 text-[10px] font-mono ${document?.exists ? "text-emerald-400" : "text-[#868584]"}`}>
                        {document?.exists ? "PRESENTE" : "SIN ARCHIVO"}
                      </span>
                    </div>
                    <pre className="min-h-20 max-h-64 overflow-auto bg-[#101012] border border-white/[0.06] rounded-lg p-3 text-[11px] leading-relaxed font-mono whitespace-pre-wrap text-[#c9c8c5]">
                      {document?.content || "Sin contenido persistente todavía."}
                    </pre>
                    {document?.updated_at && (
                      <p className="mt-2 text-[10px] font-mono text-[#646360]">
                        Actualizado: {new Date(document.updated_at * 1000).toLocaleString()}
                      </p>
                    )}
                  </section>
                );
              })}

              <form onSubmit={handleMemoryRequest} className="pt-5 mt-2 border-t border-white/[0.07]">
                <div className="flex items-center justify-between gap-4 mb-3">
                  <div>
                    <h3 className="text-xs font-mono font-semibold text-[#faf9f6]">Solicitar cambio a Hermes</h3>
                    <p className="mt-1 text-[11px] text-[#868584]">Hermes valida, aplica y registra el cambio; JARVIS no edita archivos de memoria directamente.</p>
                  </div>
                  <div className="flex bg-[#101012] border border-white/[0.08] rounded-lg p-0.5 shrink-0">
                    {(["remember", "forget"] as const).map((kind) => (
                      <button
                        key={kind}
                        type="button"
                        onClick={() => setMemoryRequestKind(kind)}
                        className={`px-2.5 py-1 rounded-md text-[10px] font-mono transition cursor-pointer ${memoryRequestKind === kind ? "bg-purple-500/20 text-purple-200" : "text-[#868584] hover:text-[#faf9f6]"}`}
                      >
                        {kind === "remember" ? "Recordar" : "Olvidar"}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="flex gap-2">
                  <input
                    value={memoryRequest}
                    onChange={(event) => setMemoryRequest(event.target.value)}
                    placeholder={memoryRequestKind === "remember" ? "Ej.: prefiero respuestas breves en español" : "Ej.: olvida que prefiero respuestas breves"}
                    className="flex-1 bg-[#101012] border border-white/[0.08] focus:border-purple-500/50 rounded-lg px-3 py-2 text-xs text-[#faf9f6] outline-none"
                  />
                  <button
                    type="submit"
                    disabled={isSubmittingMemoryRequest || !memoryRequest.trim()}
                    className="px-3 py-2 rounded-lg bg-purple-600 hover:bg-purple-500 disabled:bg-white/[0.05] disabled:text-[#868584] text-xs font-mono text-white transition cursor-pointer disabled:cursor-not-allowed"
                  >
                    {isSubmittingMemoryRequest ? "Enviando..." : "Enviar"}
                  </button>
                </div>
                {memoryRequestStatus && (
                  <p className="mt-2 text-[11px] font-mono text-[#afaeac]">{memoryRequestStatus}</p>
                )}
              </form>
            </div>
          </div>
        )}

        {/* 5. TOOLSETS & MCPS */}
        {activeSubTab === "mcps" && (
          <div className="flex-1 flex gap-5 overflow-hidden min-h-0">
            {/* Toolsets */}
            <div className="flex-1 bg-[#161618] border border-white/[0.08] rounded-2xl flex flex-col shadow-sm overflow-hidden min-h-0">
              <div className="h-11 border-b border-white/[0.08] px-5 flex items-center justify-between shrink-0 bg-[#111113]/50">
                <span className="text-xs font-mono tracking-wider text-[#faf9f6] uppercase font-semibold">
                  Toolsets del Agente ({toolsets.length})
                </span>
                <div className="flex items-center gap-3">
                  <span className="text-[11px] font-mono text-[#868584]">
                    {runtimeCapabilities.active_capabilities?.length || 0} VERIFICADOS
                  </span>
                  <button
                    type="button"
                    onClick={handleReloadSlow}
                    disabled={isReloadingSlow || isRunningAny}
                    title={isRunningAny ? "Espera a que terminen las tareas Hermes antes de recargar" : "Aplicar configuración al worker Hermes SLOW"}
                    className="px-2.5 py-1 rounded-md bg-purple-600 hover:bg-purple-500 disabled:bg-white/[0.05] disabled:text-[#868584] text-[10px] font-mono text-white transition cursor-pointer disabled:cursor-not-allowed"
                  >
                    {isReloadingSlow ? "Recargando..." : "Aplicar a SLOW"}
                  </button>
                </div>
              </div>
              {reloadSlowStatus && (
                <div className={`mx-5 mt-3 p-2.5 rounded-lg text-[11px] font-mono ${reloadSlowStatus.startsWith("No se pudo") || reloadSlowStatus.includes("rechazó") ? "bg-rose-500/10 border border-rose-500/20 text-rose-200" : "bg-emerald-500/10 border border-emerald-500/20 text-emerald-200"}`}>
                  {reloadSlowStatus}
                </div>
              )}
              <div className="flex-1 overflow-y-auto p-5 grid grid-cols-2 gap-3 min-h-0">
                {toolsets.map((t) => (
                  <div
                    key={t}
                    className="bg-[#111113] border border-white/[0.05] rounded-xl p-3 flex items-center justify-between"
                  >
                    <span className="text-xs font-mono font-medium text-[#faf9f6]">{t}</span>
                    <span className="w-2 h-2 rounded-full bg-emerald-400" />
                  </div>
                ))}
              </div>
            </div>

            {/* MCPs Management Panel */}
            <div className="w-[480px] bg-[#161618] border border-white/[0.08] rounded-2xl flex flex-col shadow-sm overflow-hidden shrink-0 min-h-0">
              <div className="h-11 border-b border-white/[0.08] px-5 flex items-center justify-between shrink-0 bg-[#111113]/50">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono tracking-wider text-[#faf9f6] uppercase font-semibold">
                    Servidores MCP ({mcps.length})
                  </span>
                  <span className="text-[10px] font-mono text-[#868584]">
                    config.yaml
                  </span>
                  <span className={`text-[10px] font-mono ${mcpStatusClass}`}>
                    {mcpStatusLabel}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setIsAddingMcp(!isAddingMcp)}
                    className="px-2.5 py-1 rounded-lg text-xs font-mono bg-purple-600 hover:bg-purple-500 text-white transition cursor-pointer flex items-center gap-1.5"
                  >
                    <span>{isAddingMcp ? "Cerrar" : "+ Añadir"}</span>
                  </button>
                  <button
                    onClick={refreshMcps}
                    className="p-1 rounded-lg bg-white/[0.05] hover:bg-white/[0.1] text-[#868584] hover:text-[#faf9f6] transition cursor-pointer text-xs"
                    title="Actualizar lista de MCPs"
                  >
                    ↻
                  </button>
                </div>
              </div>

              {/* Mensaje de acción */}
              {mcpActionMsg && (
                <div className="p-2.5 mx-4 mt-3 rounded-lg text-xs font-mono bg-purple-500/10 border border-purple-500/20 text-purple-200">
                  {mcpActionMsg}
                </div>
              )}

              {mcpStatus === "failed" && runtimeCapabilities.registry?.slow_mcp_error && (
                <div className="p-2.5 mx-4 mt-3 rounded-lg text-xs font-mono bg-red-500/10 border border-red-500/20 text-red-200">
                  {runtimeCapabilities.registry.slow_mcp_error}
                </div>
              )}

              {/* Formulario para agregar nuevo MCP */}
              {isAddingMcp && (
                <div className="p-4 mx-4 mt-3 bg-[#111113] border border-purple-500/30 rounded-xl space-y-3 shrink-0">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono font-bold text-purple-300 uppercase">
                      Nuevo Servidor MCP
                    </span>
                    <span className="text-[10px] font-mono text-[#868584]">Presets rápidos:</span>
                  </div>

                  {/* Presets Rápidos */}
                  <div className="flex flex-wrap gap-1.5">
                    {[
                      { name: "blender", cmd: "uvx", args: "blender-mcp --serve" },
                      { name: "github", cmd: "npx", args: "-y @modelcontextprotocol/server-github" },
                      { name: "filesystem", cmd: "npx", args: "-y @modelcontextprotocol/server-filesystem C:\\Users\\hp" },
                      { name: "postgres", cmd: "npx", args: "-y @modelcontextprotocol/server-postgres postgresql://localhost/db" },
                      { name: "linear", cmd: "npx", args: "-y @modelcontextprotocol/server-linear" },
                    ].map((p) => (
                      <button
                        key={p.name}
                        type="button"
                        onClick={() => {
                          setNewMcpName(p.name);
                          setNewMcpCommand(p.cmd);
                          setNewMcpArgs(p.args);
                          setNewMcpUrl("");
                        }}
                        className="px-2 py-0.5 rounded bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.06] text-[10px] font-mono text-[#afaeac] hover:text-[#faf9f6] transition cursor-pointer"
                      >
                        +{p.name}
                      </button>
                    ))}
                  </div>

                  {/* Campos */}
                  <div className="space-y-2">
                    <div>
                      <label className="block text-[10px] font-mono text-[#868584] uppercase mb-1">
                        Nombre del Servidor
                      </label>
                      <input
                        type="text"
                        value={newMcpName}
                        onChange={(e) => setNewMcpName(e.target.value)}
                        placeholder="ej: blender, github, postgres"
                        className="w-full bg-[#161619] border border-white/[0.08] focus:border-purple-500/50 rounded-lg px-2.5 py-1.5 text-xs font-mono text-[#faf9f6] outline-none"
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="block text-[10px] font-mono text-[#868584] uppercase mb-1">
                          Comando
                        </label>
                        <input
                          type="text"
                          value={newMcpCommand}
                          onChange={(e) => setNewMcpCommand(e.target.value)}
                          placeholder="uvx / npx / python"
                          className="w-full bg-[#161619] border border-white/[0.08] focus:border-purple-500/50 rounded-lg px-2.5 py-1.5 text-xs font-mono text-[#faf9f6] outline-none"
                        />
                      </div>
                      <div>
                        <label className="block text-[10px] font-mono text-[#868584] uppercase mb-1">
                          O URL (SSE/HTTP)
                        </label>
                        <input
                          type="text"
                          value={newMcpUrl}
                          onChange={(e) => setNewMcpUrl(e.target.value)}
                          placeholder="http://localhost:8000/sse"
                          className="w-full bg-[#161619] border border-white/[0.08] focus:border-purple-500/50 rounded-lg px-2.5 py-1.5 text-xs font-mono text-[#faf9f6] outline-none"
                        />
                      </div>
                    </div>

                    <div>
                      <label className="block text-[10px] font-mono text-[#868584] uppercase mb-1">
                        Argumentos
                      </label>
                      <input
                        type="text"
                        value={newMcpArgs}
                        onChange={(e) => setNewMcpArgs(e.target.value)}
                        placeholder="ej: blender-mcp --serve"
                        className="w-full bg-[#161619] border border-white/[0.08] focus:border-purple-500/50 rounded-lg px-2.5 py-1.5 text-xs font-mono text-[#faf9f6] outline-none"
                      />
                    </div>
                  </div>

                  <div className="flex items-center justify-end gap-2 pt-1">
                    <button
                      type="button"
                      onClick={() => setIsAddingMcp(false)}
                      className="px-3 py-1 text-xs font-mono text-[#868584] hover:text-[#faf9f6] transition cursor-pointer"
                    >
                      Cancelar
                    </button>
                    <button
                      type="button"
                      onClick={handleCreateMcp}
                      disabled={!newMcpName.trim()}
                      className="px-4 py-1.5 rounded-lg text-xs font-mono font-medium bg-purple-600 hover:bg-purple-500 text-white transition cursor-pointer disabled:opacity-50"
                    >
                      Guardar en config.yaml
                    </button>
                  </div>
                </div>
              )}

              {/* Lista de MCPs */}
              <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-2.5 min-h-0">
                {mcps.length === 0 ? (
                  <div className="flex-1 flex flex-col items-center justify-center text-center p-6 text-[#868584]">
                    <p className="text-xs font-mono">Sin servidores MCP externos configurados.</p>
                    <p className="text-[11px] text-[#868584]/60 mt-1">
                      Usa el botón "+ Añadir" para conectar Blender, GitHub o bases de datos.
                    </p>
                  </div>
                ) : (
                  mcps.map((m) => {
                    const isEnabled = m.enabled !== false;
                    return (
                      <div
                        key={m.name}
                        className={`bg-[#111113] border rounded-xl p-3.5 flex flex-col gap-2 transition ${
                          isEnabled
                            ? "border-white/[0.08] hover:border-purple-500/30"
                            : "border-white/[0.03] opacity-60"
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-mono font-bold text-[#faf9f6]">
                              {m.name}
                            </span>
                            <span
                              className={`text-[9px] font-mono px-2 py-0.5 rounded ${
                                isEnabled
                                  ? "bg-emerald-500/15 border border-emerald-500/30 text-emerald-300"
                                  : "bg-zinc-800 border border-zinc-700 text-zinc-400"
                              }`}
                            >
                              {isEnabled ? "ACTIVO" : "INACTIVO"}
                            </span>
                          </div>

                          <div className="flex items-center gap-2">
                            {/* Toggle */}
                            <button
                              type="button"
                              onClick={() => handleToggleMcp(m.name)}
                              className={`px-2 py-0.5 rounded text-[10px] font-mono transition cursor-pointer ${
                                isEnabled
                                  ? "text-[#868584] hover:text-amber-300 bg-white/[0.03]"
                                  : "text-emerald-400 hover:text-emerald-300 bg-emerald-500/10"
                              }`}
                              title={isEnabled ? "Deshabilitar servidor" : "Habilitar servidor"}
                            >
                              {isEnabled ? "Pausar" : "Activar"}
                            </button>

                            {/* Eliminar */}
                            <button
                              type="button"
                              onClick={() => handleDeleteMcp(m.name)}
                              className="px-2 py-0.5 rounded text-[10px] font-mono text-rose-400/70 hover:text-rose-300 bg-rose-950/20 hover:bg-rose-950/40 border border-rose-500/20 transition cursor-pointer"
                              title="Eliminar servidor de config.yaml"
                            >
                              Eliminar
                            </button>
                          </div>
                        </div>

                        {/* Detalles de comando / url */}
                        <div className="text-[11px] font-mono text-[#868584] bg-[#0c0c0e] p-2 rounded-lg border border-white/[0.04] truncate">
                          {m.command ? (
                            <span>
                              <span className="text-purple-400">{m.command}</span>{" "}
                              {Array.isArray(m.args) ? m.args.join(" ") : ""}
                            </span>
                          ) : m.url ? (
                            <span className="text-cyan-400">{m.url}</span>
                          ) : (
                            <span className="italic text-zinc-600">(sin transporte configurado)</span>
                          )}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          </div>
        )}

        {/* 6. AUTOMATIZACIONES CRON */}
        {activeSubTab === "cron" && (
          <div className="flex-1 flex gap-5 overflow-hidden min-h-0">
            <form
              onSubmit={handleCreateCron}
              className="w-[390px] shrink-0 bg-[#161618] border border-white/[0.08] rounded-2xl shadow-sm p-5 flex flex-col gap-4 overflow-y-auto"
            >
              <div className="pb-3 border-b border-white/[0.06]">
                <h2 className="text-xs font-mono font-semibold tracking-wider text-[#faf9f6] uppercase">Nueva automatización</h2>
                <p className="mt-1 text-[11px] text-[#868584] leading-relaxed">Se crea en el scheduler nativo de Hermes con entrega local a JARVIS.</p>
              </div>

              <label className="block">
                <span className="block text-[10px] font-mono text-[#868584] uppercase mb-1.5">Nombre</span>
                <input
                  value={cronName}
                  onChange={(event) => setCronName(event.target.value)}
                  placeholder="Informe diario"
                  className="w-full bg-[#111113] border border-white/[0.08] focus:border-purple-500/50 rounded-lg px-3 py-2 text-xs text-[#faf9f6] outline-none"
                />
              </label>

              <label className="block">
                <span className="block text-[10px] font-mono text-[#868584] uppercase mb-1.5">Horario Hermes</span>
                <input
                  required
                  value={cronSchedule}
                  onChange={(event) => setCronSchedule(event.target.value)}
                  placeholder="cada día a las 08:00"
                  className="w-full bg-[#111113] border border-white/[0.08] focus:border-purple-500/50 rounded-lg px-3 py-2 text-xs text-[#faf9f6] outline-none"
                />
              </label>

              <label className="block flex-1 min-h-32">
                <span className="block text-[10px] font-mono text-[#868584] uppercase mb-1.5">Instrucción</span>
                <textarea
                  required
                  value={cronPrompt}
                  onChange={(event) => setCronPrompt(event.target.value)}
                  placeholder="Revisa mi agenda de hoy y prepara un resumen breve."
                  className="w-full h-32 resize-none bg-[#111113] border border-white/[0.08] focus:border-purple-500/50 rounded-lg px-3 py-2 text-xs text-[#faf9f6] placeholder-[#868584]/60 outline-none leading-relaxed"
                />
              </label>

              <button
                type="submit"
                disabled={isSavingCron || !cronPrompt.trim() || !cronSchedule.trim()}
                className="w-full py-2.5 rounded-lg bg-purple-600 hover:bg-purple-500 disabled:bg-white/[0.05] disabled:text-[#868584] text-white text-xs font-mono font-medium transition cursor-pointer disabled:cursor-not-allowed"
              >
                {isSavingCron ? "Creando en Hermes..." : "Crear automatización"}
              </button>
            </form>

            <div className="flex-1 bg-[#161618] border border-white/[0.08] rounded-2xl flex flex-col shadow-sm overflow-hidden min-h-0">
              <div className="h-11 border-b border-white/[0.08] px-5 flex items-center justify-between shrink-0 bg-[#111113]/50">
                <div className="flex items-center gap-3">
                  <span className="text-xs font-mono tracking-wider text-[#faf9f6] uppercase font-semibold">Scheduler de Hermes</span>
                  <span className="text-[10px] font-mono text-[#868584]">{cronJobs.length} registradas</span>
                </div>
                <button
                  type="button"
                  onClick={refreshCron}
                  className="p-1.5 rounded-lg bg-white/[0.05] hover:bg-white/[0.1] text-[#868584] hover:text-[#faf9f6] transition cursor-pointer"
                  title="Actualizar automatizaciones"
                >
                  ↻
                </button>
              </div>

              {(cronStatus || cronError) && (
                <div className={`mx-5 mt-4 p-3 rounded-lg text-xs font-mono ${cronError ? "bg-rose-500/10 border border-rose-500/20 text-rose-200" : "bg-emerald-500/10 border border-emerald-500/20 text-emerald-200"}`}>
                  {cronError || cronStatus}
                </div>
              )}

              <div className="flex-1 overflow-y-auto px-5 py-4 min-h-0">
                {cronJobs.length === 0 ? (
                  <div className="h-full flex flex-col items-center justify-center text-center text-[#868584]">
                    <p className="text-xs font-mono">No hay automatizaciones registradas.</p>
                    <p className="mt-1 text-[11px]">Crea una rutina para que Hermes la ejecute según su horario.</p>
                  </div>
                ) : (
                  <div className="divide-y divide-white/[0.07]">
                    {cronJobs.map((job) => {
                      const isPaused = job.state === "paused" || job.enabled === false;
                      return (
                        <article key={job.id} className="py-4 first:pt-0">
                          <div className="flex items-start justify-between gap-5">
                            <div className="min-w-0">
                              <div className="flex items-center gap-2">
                                <h3 className="text-xs font-mono font-semibold text-[#faf9f6] truncate">{job.name || "Automatización sin nombre"}</h3>
                                <span className={`shrink-0 text-[10px] font-mono ${isPaused ? "text-amber-300" : "text-emerald-400"}`}>
                                  {isPaused ? "PAUSADA" : "ACTIVA"}
                                </span>
                              </div>
                              <p className="mt-2 text-xs leading-relaxed text-[#c9c8c5] whitespace-pre-wrap">{job.prompt || "Sin instrucción registrada."}</p>
                              <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[10px] font-mono text-[#868584]">
                                <span>Horario: {job.schedule_display || "No disponible"}</span>
                                <span>Próxima: {job.next_run_at ? new Date(job.next_run_at).toLocaleString() : "sin programar"}</span>
                                <span>Última: {job.last_run_at ? new Date(job.last_run_at).toLocaleString() : "sin ejecuciones"}</span>
                                {job.last_status && <span>Resultado: {job.last_status}</span>}
                              </div>
                              {job.last_error && <p className="mt-2 text-[11px] font-mono text-rose-300">Error: {job.last_error}</p>}
                            </div>
                            <div className="shrink-0 flex items-center gap-2 flex-wrap justify-end">
                              <button
                                type="button"
                                onClick={() => handleCronAction(job.id, "trigger")}
                                className="px-2.5 py-1 rounded-md bg-white/[0.05] hover:bg-white/[0.1] text-[10px] font-mono text-[#faf9f6] transition cursor-pointer"
                              >
                                Ejecutar
                              </button>
                              <button
                                type="button"
                                onClick={() => handleCronAction(job.id, isPaused ? "resume" : "pause")}
                                className={`px-2.5 py-1 rounded-md text-[10px] font-mono transition cursor-pointer ${isPaused ? "bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20" : "bg-amber-500/10 text-amber-300 hover:bg-amber-500/20"}`}
                              >
                                {isPaused ? "Reanudar" : "Pausar"}
                              </button>
                              <button
                                type="button"
                                onClick={() => startEditingCron(job)}
                                className="px-2.5 py-1 rounded-md bg-white/[0.05] hover:bg-white/[0.1] text-[10px] font-mono text-[#faf9f6] transition cursor-pointer"
                              >
                                Editar
                              </button>
                              <button
                                type="button"
                                onClick={() => handleToggleCronOutputs(job.id)}
                                className="px-2.5 py-1 rounded-md bg-white/[0.05] hover:bg-white/[0.1] text-[10px] font-mono text-[#faf9f6] transition cursor-pointer"
                              >
                                {loadingCronOutputId === job.id ? "Cargando..." : cronOutputs[job.id] ? "Ocultar historial" : "Historial"}
                              </button>
                              <button
                                type="button"
                                onClick={() => handleDeleteCron(job)}
                                className="px-2.5 py-1 rounded-md bg-rose-500/10 hover:bg-rose-500/20 text-[10px] font-mono text-rose-300 transition cursor-pointer"
                              >
                                Eliminar
                              </button>
                            </div>
                          </div>
                          {editingCronId === job.id && (
                            <form onSubmit={handleSaveCronEdit} className="mt-4 pt-4 border-t border-white/[0.07] grid gap-3">
                              <div className="grid grid-cols-2 gap-3">
                                <input
                                  value={editCronName}
                                  onChange={(event) => setEditCronName(event.target.value)}
                                  placeholder="Nombre"
                                  className="bg-[#101012] border border-white/[0.08] focus:border-purple-500/50 rounded-lg px-3 py-2 text-xs text-[#faf9f6] outline-none"
                                />
                                <input
                                  required
                                  value={editCronSchedule}
                                  onChange={(event) => setEditCronSchedule(event.target.value)}
                                  placeholder="Horario"
                                  className="bg-[#101012] border border-white/[0.08] focus:border-purple-500/50 rounded-lg px-3 py-2 text-xs text-[#faf9f6] outline-none"
                                />
                              </div>
                              <textarea
                                required
                                value={editCronPrompt}
                                onChange={(event) => setEditCronPrompt(event.target.value)}
                                className="h-24 resize-none bg-[#101012] border border-white/[0.08] focus:border-purple-500/50 rounded-lg px-3 py-2 text-xs text-[#faf9f6] outline-none leading-relaxed"
                              />
                              <div className="flex justify-end gap-2">
                                <button type="button" onClick={() => setEditingCronId(null)} className="px-3 py-1.5 text-[10px] font-mono text-[#868584] hover:text-[#faf9f6] transition cursor-pointer">Cancelar</button>
                                <button type="submit" className="px-3 py-1.5 rounded-md bg-purple-600 hover:bg-purple-500 text-[10px] font-mono text-white transition cursor-pointer">Guardar cambios</button>
                              </div>
                            </form>
                          )}
                          {cronOutputs[job.id] && (
                            <div className="mt-4 pt-4 border-t border-white/[0.07] space-y-3">
                              {cronOutputs[job.id].length === 0 ? (
                                <p className="text-[11px] font-mono text-[#868584]">Hermes todavía no ha guardado salida para esta automatización.</p>
                              ) : cronOutputs[job.id].map((output) => (
                                <div key={output.name}>
                                  <p className="mb-1 text-[10px] font-mono text-[#868584]">{new Date(output.created_at * 1000).toLocaleString()}</p>
                                  <pre className="max-h-56 overflow-auto bg-[#101012] border border-white/[0.06] rounded-lg p-3 text-[11px] leading-relaxed font-mono whitespace-pre-wrap text-[#c9c8c5]">{output.content}</pre>
                                </div>
                              ))}
                            </div>
                          )}
                        </article>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* 7. AUTONOMÍA */}
        {activeSubTab === "autonomy" && (
          <div className="flex-1 grid grid-cols-2 gap-5 overflow-hidden min-h-0">
            <div className="bg-[#161618] border border-white/[0.08] rounded-2xl flex flex-col shadow-sm p-6 gap-5 overflow-y-auto">
              <div className="flex items-center justify-between pb-3 border-b border-white/[0.06]">
                <span className="text-xs font-mono font-bold tracking-wider text-[#faf9f6] uppercase">
                  System Sentinel (Proactivo)
                </span>
                <span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${autonomyStatus.sentinel?.running ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/20" : "bg-amber-500/10 text-amber-300 border-amber-500/20"}`}>
                  {autonomyStatus.sentinel?.running ? "ACTIVO" : "DETENIDO"}
                </span>
              </div>
              <div className="flex flex-col gap-3.5">
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

            <div className="bg-[#161618] border border-white/[0.08] rounded-2xl flex flex-col shadow-sm p-6 gap-5 overflow-y-auto">
              <div className="flex items-center justify-between pb-3 border-b border-white/[0.06]">
                <span className="text-xs font-mono font-bold tracking-wider text-[#faf9f6] uppercase">
                  Hermes Autonomous Scheduler
                </span>
                <span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${autonomyStatus.scheduler?.running ? "bg-cyan-500/10 text-cyan-300 border-cyan-500/20" : "bg-amber-500/10 text-amber-300 border-amber-500/20"}`}>
                  {autonomyStatus.scheduler?.running ? "CRON ACTIVO" : "CRON DETENIDO"}
                </span>
              </div>
              <div className="flex flex-col gap-3.5">
                <div className="flex items-center justify-between py-2 border-b border-white/[0.04]">
                  <span className="text-xs font-mono text-[#868584]">Intervalo de Evaluación</span>
                  <span className="text-xs font-mono text-[#faf9f6]">
                    {autonomyStatus.scheduler?.interval_seconds ? `Cada ${autonomyStatus.scheduler.interval_seconds} segundos` : "No disponible"}
                  </span>
                </div>
                <div className="flex items-center justify-between py-2 border-b border-white/[0.04]">
                  <span className="text-xs font-mono text-[#868584]">Routinas de Memoria</span>
                  <span className="text-xs font-mono text-[#faf9f6]">Consolidación de sesiones por Hermes</span>
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

        {/* 8. AJUSTES DE HERMES */}
        {activeSubTab === "settings" && (
          <div className="flex-1 flex gap-5 overflow-hidden min-h-0">
            {/* Directivas Operativas y Seguridad */}
            <div className="w-[450px] bg-[#161618] border border-white/[0.08] rounded-2xl flex flex-col shadow-sm p-5 gap-4 overflow-y-auto shrink-0">
              <div className="flex items-center justify-between pb-2 border-b border-white/[0.06]">
                <span className="text-xs font-mono font-bold tracking-wider text-[#faf9f6] uppercase">
                  Directivas Operativas
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-500/10 text-purple-300 border border-purple-500/20">
                  COMPORTAMIENTO
                </span>
              </div>

              {/* Switches de Comportamiento */}
              <div className="flex flex-col gap-2.5">
                {/* Memoria */}
                <div
                  onClick={() => setCfgMemoryEnabled(!cfgMemoryEnabled)}
                  className={`p-3 rounded-xl border transition cursor-pointer flex items-center justify-between ${
                    cfgMemoryEnabled
                      ? "bg-purple-500/10 border-purple-500/30"
                      : "bg-[#111113] border-white/[0.04] opacity-70"
                  }`}
                >
                  <div className="flex flex-col gap-0.5 pr-2">
                    <span className="text-xs font-mono font-bold text-[#faf9f6]">
                      Memoria Persistente a Largo Plazo
                    </span>
                    <span className="text-[10px] text-[#868584]">
                      Permite a Hermes recordar hechos y preferencias entre diferentes sesiones.
                    </span>
                  </div>
                  <div
                    className={`w-8 h-4.5 rounded-full p-0.5 shrink-0 transition-colors ${
                      cfgMemoryEnabled ? "bg-purple-500" : "bg-white/[0.1]"
                    }`}
                  >
                    <div
                      className={`w-3.5 h-3.5 rounded-full bg-white transition-transform ${
                        cfgMemoryEnabled ? "translate-x-3.5" : "translate-x-0"
                      }`}
                    />
                  </div>
                </div>

                {/* Soul / Identidad */}
                <div
                  onClick={() => setCfgSoulEnabled(!cfgSoulEnabled)}
                  className={`p-3 rounded-xl border transition cursor-pointer flex items-center justify-between ${
                    cfgSoulEnabled
                      ? "bg-purple-500/10 border-purple-500/30"
                      : "bg-[#111113] border-white/[0.04] opacity-70"
                  }`}
                >
                  <div className="flex flex-col gap-0.5 pr-2">
                    <span className="text-xs font-mono font-bold text-[#faf9f6]">
                      Identidad & Directivas (Soul)
                    </span>
                    <span className="text-[10px] text-[#868584]">
                      Aplica las directrices autónomas, resolución metódica y personalidad de Hermes.
                    </span>
                  </div>
                  <div
                    className={`w-8 h-4.5 rounded-full p-0.5 shrink-0 transition-colors ${
                      cfgSoulEnabled ? "bg-purple-500" : "bg-white/[0.1]"
                    }`}
                  >
                    <div
                      className={`w-3.5 h-3.5 rounded-full bg-white transition-transform ${
                        cfgSoulEnabled ? "translate-x-3.5" : "translate-x-0"
                      }`}
                    />
                  </div>
                </div>

                {/* Strict Gate */}
                <div
                  onClick={() => setCfgStrictGate(!cfgStrictGate)}
                  className={`p-3 rounded-xl border transition cursor-pointer flex items-center justify-between ${
                    cfgStrictGate
                      ? "bg-purple-500/10 border-purple-500/30"
                      : "bg-[#111113] border-white/[0.04] opacity-70"
                  }`}
                >
                  <div className="flex flex-col gap-0.5 pr-2">
                    <span className="text-xs font-mono font-bold text-[#faf9f6]">
                      Filtro Estricto de Intención
                    </span>
                    <span className="text-[10px] text-[#868584]">
                      Evita que Hermes despache tareas por accidente al escuchar frases ambiguas.
                    </span>
                  </div>
                  <div
                    className={`w-8 h-4.5 rounded-full p-0.5 shrink-0 transition-colors ${
                      cfgStrictGate ? "bg-purple-500" : "bg-white/[0.1]"
                    }`}
                  >
                    <div
                      className={`w-3.5 h-3.5 rounded-full bg-white transition-transform ${
                        cfgStrictGate ? "translate-x-3.5" : "translate-x-0"
                      }`}
                    />
                  </div>
                </div>
              </div>

              {/* Timeout Slider */}
              <div className="flex flex-col gap-1.5 pt-1">
                <div className="flex items-center justify-between text-[11px] font-mono">
                  <span className="text-[#868584] uppercase">Timeout de Tareas Complejas</span>
                  <span className="text-[#faf9f6]">{cfgTimeout} segundos</span>
                </div>
                <input
                  type="range"
                  min="30"
                  max="600"
                  step="15"
                  value={cfgTimeout}
                  onChange={(e) => setCfgTimeout(Number(e.target.value))}
                  className="w-full accent-purple-500 cursor-pointer"
                />
              </div>

              {/* KeyRotator Pool */}
              <div className="pt-2 border-t border-white/[0.06] flex flex-col gap-2">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-mono text-[#868584] uppercase">
                    KeyRotator Pool
                  </span>
                  <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded">
                    {keyPoolCount} Claves Activas
                  </span>
                </div>
                <input
                  type="password"
                  value={cfgApiKey}
                  onChange={(e) => setCfgApiKey(e.target.value)}
                  placeholder="AIzaSy... (añadir nueva clave al pool de rotación)"
                  className="bg-[#111113] border border-white/[0.08] focus:border-purple-500/50 rounded-xl px-3 py-2 text-xs font-mono text-[#faf9f6] outline-none"
                />
              </div>

              {/* Botón Guardar */}
              <div className="mt-auto pt-3 border-t border-white/[0.06] flex flex-col gap-2.5">
                <button
                  onClick={handleSaveConfig}
                  disabled={isSavingConfig}
                  className="w-full py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-mono font-medium text-xs tracking-wider uppercase transition shadow-lg shadow-purple-900/30 cursor-pointer disabled:opacity-50"
                >
                  {isSavingConfig ? "Guardando en .env..." : "Guardar Directivas"}
                </button>

                {configSaveMsg && (
                  <div
                    className={`p-2 rounded-lg text-xs font-mono ${
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

            {/* Matriz de Toolsets */}
            <div className="flex-1 bg-[#161618] border border-white/[0.08] rounded-2xl flex flex-col shadow-sm p-5 gap-4 overflow-y-auto min-h-0">
              <div className="flex items-center justify-between pb-2 border-b border-white/[0.06]">
                <span className="text-xs font-mono font-bold tracking-wider text-[#faf9f6] uppercase">
                  Toolsets Habilitados ({cfgEnabledToolsets.length} / {ALL_POSSIBLE_TOOLSETS.length})
                </span>
                <span className="text-[11px] font-mono text-[#868584]">
                  Haz clic para activar o desactivar
                </span>
              </div>

              <div className="grid grid-cols-2 gap-2.5">
                {ALL_POSSIBLE_TOOLSETS.map((t) => {
                  const isEnabled = cfgEnabledToolsets.includes(t);
                  return (
                    <button
                      key={t}
                      type="button"
                      onClick={() => toggleToolset(t)}
                      className={`p-3 rounded-xl border text-left transition flex items-center justify-between cursor-pointer ${
                        isEnabled
                          ? "bg-purple-500/10 border-purple-500/30 hover:border-purple-500/50"
                          : "bg-[#111113] border-white/[0.04] opacity-50 hover:opacity-75"
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
                        className={`w-8 h-4.5 rounded-full p-0.5 transition-colors duration-200 ease-in-out ${
                          isEnabled ? "bg-purple-500" : "bg-white/[0.1]"
                        }`}
                      >
                        <div
                          className={`w-3.5 h-3.5 rounded-full bg-white transition-transform duration-200 ease-in-out ${
                            isEnabled ? "translate-x-3.5" : "translate-x-0"
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
