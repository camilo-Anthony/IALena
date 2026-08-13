import React, { useState, useEffect, useRef } from "react";
import { useJarvisStore } from "../store/jarvisStore";
import { jarvisAPI } from "../hooks/useJarvisAPI";
import type { LogEntry } from "../types";

export function PanelView() {
  const status = useJarvisStore((s) => s.status);
  const tasks = useJarvisStore((s) => s.tasks);
  const config = useJarvisStore((s) => s.config);
  const storeLogs = useJarvisStore((s) => s.logs);
  const setConfig = useJarvisStore((s) => s.setConfig);
  const appendLog = useJarvisStore((s) => s.appendLog);

  const [activeTab, setActiveTab] = useState<"diagnostico" | "tareas" | "config" | "logs">("diagnostico");
  
  // Variables locales para formulario de configuración
  const [formData, setFormData] = useState<Record<string, string>>({});
  const [saveStatus, setSaveStatus] = useState<string | null>(null);

  // Cargar configuración local cuando el store la reciba
  useEffect(() => {
    if (config) {
      const cleanForm: Record<string, string> = {};
      Object.keys(config).forEach((key) => {
        cleanForm[key] = config[key] || "";
      });
      setFormData(cleanForm);
    }
  }, [config]);

  // Sincronizar logs en primer montado si no hay ninguno
  useEffect(() => {
    async function syncLogs() {
      try {
        const res = await jarvisAPI.getLogs(50);
        res.logs.forEach((log) => {
          appendLog(log);
        });
      } catch (e) {
        console.error(e);
      }
    }
    if (storeLogs.length === 0) {
      syncLogs();
    }
  }, [appendLog, storeLogs.length]);

  const handleInputChange = (key: string, val: string) => {
    setFormData((prev) => ({ ...prev, [key]: val }));
  };

  const handleSaveConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaveStatus("Guardando...");
    try {
      // Filtrar campos vacíos o sin modificar para optimizar
      const updates: Record<string, string> = {};
      Object.keys(formData).forEach((k) => {
        if (formData[k] !== config?.[k]) {
          updates[k] = formData[k];
        }
      });

      if (Object.keys(updates).length === 0) {
        setSaveStatus("Sin cambios para guardar.");
        setTimeout(() => setSaveStatus(null), 2500);
        return;
      }

      await jarvisAPI.updateConfig(updates);
      // Recargar configuración del backend para reflejar los cambios enmascarados
      const freshConfig = await jarvisAPI.getConfig();
      setConfig(freshConfig);

      setSaveStatus("Configuración guardada exitosamente.");
      setTimeout(() => setSaveStatus(null), 3000);
    } catch (err: unknown) {
      setSaveStatus(`Error: ${err instanceof Error ? err.message : String(err)}`);
    }
  };

  // Acciones operativas
  const handleRestartVoice = async () => {
    if (window.confirm("¿Seguro que deseas reiniciar el módulo de voz Live?")) {
      try {
        await jarvisAPI.restartVoice();
        alert("Petición de reinicio enviada correctamente.");
      } catch (e: unknown) {
        alert(`Error: ${e instanceof Error ? e.message : String(e)}`);
      }
    }
  };

  const handleShutdown = async () => {
    if (window.confirm("¡ATENCIÓN! ¿Estás completamente seguro de apagar el núcleo de JARVIS?")) {
      try {
        await jarvisAPI.shutdown();
        alert("Señal de apagado enviada.");
      } catch (e: unknown) {
        alert(`Error: ${e instanceof Error ? e.message : String(e)}`);
      }
    }
  };

  return (
    <div className="w-full h-full flex flex-col bg-[#040d1a] border border-cyan-500/20 rounded-lg overflow-hidden text-[#e0f4ff] font-sans">
      {/* Navegación Panel Tabs */}
      <div className="flex border-b border-cyan-500/20 bg-slate-950/60 p-2 gap-1.5 shrink-0">
        <button
          onClick={() => setActiveTab("diagnostico")}
          className={`px-4 py-1.5 text-xs font-mono tracking-wider rounded transition cursor-pointer ${
            activeTab === "diagnostico"
              ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
              : "text-slate-400 hover:text-cyan-400"
          }`}
        >
          DIAGNÓSTICO
        </button>
        <button
          onClick={() => setActiveTab("tareas")}
          className={`px-4 py-1.5 text-xs font-mono tracking-wider rounded transition cursor-pointer ${
            activeTab === "tareas"
              ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
              : "text-slate-400 hover:text-cyan-400"
          }`}
        >
          TAREAS / COLA
        </button>
        <button
          onClick={() => setActiveTab("config")}
          className={`px-4 py-1.5 text-xs font-mono tracking-wider rounded transition cursor-pointer ${
            activeTab === "config"
              ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
              : "text-slate-400 hover:text-cyan-400"
          }`}
        >
          CONFIGURACIÓN
        </button>
        <button
          onClick={() => setActiveTab("logs")}
          className={`px-4 py-1.5 text-xs font-mono tracking-wider rounded transition cursor-pointer ${
            activeTab === "logs"
              ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
              : "text-slate-400 hover:text-cyan-400"
          }`}
        >
          LOGS DEL SISTEMA
        </button>
      </div>

      {/* Contenido tab */}
      <div className="flex-1 overflow-y-auto p-5 min-h-0 bg-[#020710]/40">
        {activeTab === "diagnostico" && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {/* Card Kernel */}
              <div className="bg-slate-950/40 border border-cyan-500/10 rounded p-4">
                <div className="text-[10px] font-mono tracking-widest text-slate-400 uppercase">Estado del Núcleo</div>
                <div className="text-xl font-mono mt-2 flex items-center gap-2">
                  <span className={`w-3.5 h-3.5 rounded-full ${status?.kernel_ready ? "bg-green-500" : "bg-red-500"}`} />
                  {status?.kernel_ready ? "KERNEL ACTIVO" : "KERNEL APAGADO"}
                </div>
                <div className="text-xs text-slate-400 mt-2">
                  Uptime: {status?.uptime_seconds ? `${Math.round(status.uptime_seconds)}s` : "—"}
                </div>
              </div>

              {/* Card Live */}
              <div className="bg-slate-950/40 border border-cyan-500/10 rounded p-4">
                <div className="text-[10px] font-mono tracking-widest text-slate-400 uppercase">Gemini Live Connection</div>
                <div className="text-xl font-mono mt-2 flex items-center gap-2">
                  <span className={`w-3.5 h-3.5 rounded-full ${status?.live_connected ? "bg-green-500" : "bg-red-500"}`} />
                  {status?.live_connected ? "LIVE CONECTADO" : "LIVE OFFLINE"}
                </div>
                <button
                  onClick={async () => {
                    const res = await jarvisAPI.testLive();
                    alert(res.live_connected ? "Conectividad Live verificada exitosamente." : "Sin conexión Live.");
                  }}
                  className="mt-3 px-3 py-1 bg-slate-900 border border-cyan-500/20 hover:border-cyan-400 text-[10px] font-mono rounded cursor-pointer transition"
                >
                  PROBAR ENLACE LIVE
                </button>
              </div>

              {/* Card Brain Rotator */}
              <div className="bg-slate-950/40 border border-cyan-500/10 rounded p-4">
                <div className="text-[10px] font-mono tracking-widest text-slate-400 uppercase">Key Rotator (Hermes)</div>
                {status?.key_rotator ? (
                  <div className="mt-2 space-y-1">
                    <div className="text-sm font-mono">Pool: {status.key_rotator.pool_size} keys</div>
                    <div className="text-xs text-slate-400">Peticiones: {status.key_rotator.call_count}</div>
                    <div className="text-[10px] text-cyan-400 font-mono mt-1">Activa: {status.key_rotator.active_key_masked}</div>
                  </div>
                ) : (
                  <div className="text-sm text-slate-400 mt-2">No disponible</div>
                )}
              </div>
            </div>

            {/* Acciones Críticas */}
            <div className="bg-slate-950/40 border border-red-500/20 rounded p-4">
              <div className="text-[10px] font-mono tracking-widest text-red-400 uppercase mb-3">Acciones de Emergencia</div>
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={handleRestartVoice}
                  className="px-4 py-2 bg-slate-900 border border-cyan-500/30 hover:border-cyan-400 text-cyan-300 text-xs font-mono rounded cursor-pointer transition"
                >
                  RECOMPILAR/RECONECTAR VOZ
                </button>
                <button
                  onClick={handleShutdown}
                  className="px-4 py-2 bg-red-950/40 border border-red-500/40 hover:border-red-400 text-red-300 text-xs font-mono rounded cursor-pointer transition"
                >
                  APAGAR INSTANCIA DE NÚCLEO
                </button>
              </div>
            </div>
          </div>
        )}

        {activeTab === "tareas" && (
          <div className="space-y-4">
            <div className="bg-slate-950/40 border border-cyan-500/10 rounded p-4">
              <h3 className="text-sm font-mono text-cyan-400 tracking-wider mb-3">Carril Lento (Hermes SLOW)</h3>
              {tasks?.running_slow.length === 0 ? (
                <div className="text-xs text-slate-400 italic">No hay tareas en el carril lento</div>
              ) : (
                <div className="space-y-2">
                  {tasks?.running_slow.map((t) => (
                    <div key={t.task_id} className="bg-amber-500/10 border border-amber-500/20 p-2.5 rounded text-xs font-mono flex justify-between items-center">
                      <div>
                        <span className="text-amber-400 font-bold">[ACTIVA]</span> {t.prompt}
                      </div>
                      <span className="text-[10px] text-slate-400">ID: {t.task_id}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="bg-slate-950/40 border border-cyan-500/10 rounded p-4">
              <h3 className="text-sm font-mono text-cyan-400 tracking-wider mb-3">Carril Rápido (Fast Hermes)</h3>
              {tasks?.running_fast.length === 0 ? (
                <div className="text-xs text-slate-400 italic">No hay tareas activas rápidas</div>
              ) : (
                <div className="space-y-2">
                  {tasks?.running_fast.map((t) => (
                    <div key={t.task_id} className="bg-cyan-500/10 border border-cyan-500/20 p-2.5 rounded text-xs font-mono flex justify-between items-center">
                      <div>
                        <span className="text-cyan-400 font-bold">[PROCESANDO]</span> {t.prompt}
                      </div>
                      <span className="text-[10px] text-slate-400">ID: {t.task_id}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="bg-slate-950/40 border border-cyan-500/10 rounded p-4">
              <h3 className="text-sm font-mono text-cyan-400 tracking-wider mb-3">Historial de tareas</h3>
              {tasks?.recent.length === 0 ? (
                <div className="text-xs text-slate-400 italic">Ninguna tarea registrada en el historial</div>
              ) : (
                <div className="space-y-1.5">
                  {tasks?.recent.slice(0, 10).map((t) => (
                    <div key={t.task_id} className="bg-slate-900/60 p-2 rounded text-xs font-mono flex justify-between items-center text-slate-300">
                      <div className="truncate max-w-lg">
                        <span className={`mr-2 ${t.state === "completed" ? "text-green-400" : t.state === "failed" ? "text-red-400" : "text-slate-400"}`}>
                          ● {t.state.toUpperCase()}
                        </span>
                        {t.prompt}
                      </div>
                      <span className="text-[10px] text-slate-500 shrink-0">{t.task_id}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === "config" && (
          <form onSubmit={handleSaveConfig} className="space-y-4">
            <div className="bg-slate-950/40 border border-cyan-500/10 rounded p-4 space-y-4">
              <h3 className="text-sm font-mono text-cyan-400 tracking-wider border-b border-cyan-500/10 pb-2">Parámetros de Modelos y API</h3>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-[10px] font-mono text-slate-400 uppercase mb-1">Model Live</label>
                  <input
                    type="text"
                    value={formData.MODEL_LIVE || ""}
                    onChange={(e) => handleInputChange("MODEL_LIVE", e.target.value)}
                    className="w-full bg-slate-950 border border-cyan-500/20 focus:border-cyan-400 rounded p-2 text-xs font-mono text-cyan-200 outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-mono text-slate-400 uppercase mb-1">Model Brain</label>
                  <input
                    type="text"
                    value={formData.MODEL_BRAIN || ""}
                    onChange={(e) => handleInputChange("MODEL_BRAIN", e.target.value)}
                    className="w-full bg-slate-950 border border-cyan-500/20 focus:border-cyan-400 rounded p-2 text-xs font-mono text-cyan-200 outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-mono text-slate-400 uppercase mb-1">Assistant Name</label>
                  <input
                    type="text"
                    value={formData.ASSISTANT_NAME || ""}
                    onChange={(e) => handleInputChange("ASSISTANT_NAME", e.target.value)}
                    className="w-full bg-slate-950 border border-cyan-500/20 focus:border-cyan-400 rounded p-2 text-xs font-mono text-cyan-200 outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-mono text-slate-400 uppercase mb-1">User Name</label>
                  <input
                    type="text"
                    value={formData.USER_NAME || ""}
                    onChange={(e) => handleInputChange("USER_NAME", e.target.value)}
                    className="w-full bg-slate-950 border border-cyan-500/20 focus:border-cyan-400 rounded p-2 text-xs font-mono text-cyan-200 outline-none"
                  />
                </div>
              </div>
            </div>

            <div className="bg-slate-950/40 border border-cyan-500/10 rounded p-4 space-y-4">
              <h3 className="text-sm font-mono text-cyan-400 tracking-wider border-b border-cyan-500/10 pb-2">Claves API (Enmascaradas en UI)</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-[10px] font-mono text-slate-400 uppercase mb-1">Gemini API Key</label>
                  <input
                    type="text"
                    placeholder="Escribe para actualizar..."
                    value={formData.GEMINI_API_KEY || ""}
                    onChange={(e) => handleInputChange("GEMINI_API_KEY", e.target.value)}
                    className="w-full bg-slate-950 border border-cyan-500/20 focus:border-cyan-400 rounded p-2 text-xs font-mono text-cyan-200 outline-none"
                  />
                </div>
              </div>
            </div>

            <div className="flex justify-between items-center shrink-0">
              <div className="text-xs font-mono text-cyan-400">{saveStatus}</div>
              <button
                type="submit"
                className="px-6 py-2 bg-cyan-500/20 border border-cyan-500/40 hover:border-cyan-400 text-cyan-300 text-xs font-mono rounded cursor-pointer transition uppercase"
              >
                Guardar Configuración
              </button>
            </div>
          </form>
        )}

        {activeTab === "logs" && (
          <div className="bg-slate-950/40 border border-cyan-500/10 rounded p-3 h-full flex flex-col min-h-[300px]">
            <div className="text-[10px] font-mono tracking-widest text-slate-400 uppercase border-b border-cyan-500/10 pb-2 mb-2 flex justify-between">
              <span>Bitácora del Sistema en tiempo real</span>
              <button
                onClick={() => useJarvisStore.getState().clearLogs()}
                className="text-[9px] text-red-400 hover:text-red-300 font-mono transition cursor-pointer"
              >
                LIMPIAR LOGS
              </button>
            </div>
            <div className="flex-1 font-mono text-[11px] text-cyan-200/90 space-y-1 overflow-y-auto pr-2 min-h-0 select-text">
              {storeLogs.length === 0 ? (
                <div className="text-slate-500 italic">No hay logs en el búfer local</div>
              ) : (
                storeLogs.map((log, idx) => (
                  <div key={idx} className="leading-relaxed hover:bg-cyan-950/10 rounded p-0.5 transition">
                    <span className="text-slate-500 mr-2">
                      [{new Date(log.ts * 1000).toLocaleTimeString("es-MX", { hour12: false })}]
                    </span>
                    <span className={`mr-2 px-1 text-[9px] rounded font-bold ${
                      log.level === "ERROR"
                        ? "bg-red-500/20 text-red-400"
                        : log.level === "WARNING"
                        ? "bg-amber-500/20 text-amber-400"
                        : "bg-cyan-500/10 text-cyan-400"
                    }`}>
                      {log.level}
                    </span>
                    <span className="text-slate-400 mr-2">&lt;{log.source}&gt;</span>
                    {log.message}
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
