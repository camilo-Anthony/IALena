import React, { useMemo } from "react";
import { useJarvisStore } from "../../store/jarvisStore";
import { jarvisAPI } from "../../hooks/useJarvisAPI";
import type { OrbState } from "../../types";

const ORB_STATE_HUD_LABELS: Record<OrbState, string> = {
  dormant: "SISTEMA INACTIVO",
  listening: "ESCUCHANDO COMPRENSIÓN DE VOZ",
  speaking: "TRANSMITIENDO ENLACE S2S",
  thinking_fast: "ANÁLISIS COGNITIVO FAST",
  working_slow: "EJECUCIÓN NÚCLEO SLOW",
  reconnecting: "RECONEXIÓN PROTOCOLO LIVE",
  confirmation_pending: "ESPERANDO VERIFICACIÓN DE INTENCIÓN",
  delivery_waiting: "ENTREGANDO RESPUESTA DE TAREA",
  error: "FALLO DE SISTEMA — ATENCIÓN REQUERIDA",
};

interface OrbHUDProps {
  state: OrbState;
}

export function OrbHUD({ state }: OrbHUDProps) {
  const wsConnected = useJarvisStore((s) => s.wsConnected);
  const status      = useJarvisStore((s) => s.status);
  const tasks       = useJarvisStore((s) => s.tasks);

  // Obtener tareas activas en cola lenta o rápida
  const activeSlow = tasks?.running_slow || [];
  const activeFast = tasks?.running_fast || [];
  const pending    = tasks?.pending_slow || [];

  const handleMute = async () => {
    try {
      await jarvisAPI.toggleMute();
    } catch (e) {
      console.error(e);
    }
  };

  const handleWake = async () => {
    try {
      if (state === "dormant") {
        await jarvisAPI.wake();
      } else {
        await jarvisAPI.sleep();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleCancel = async () => {
    try {
      await jarvisAPI.cancelTask();
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="absolute inset-0 flex flex-col justify-between p-6 pointer-events-none select-none z-10">
      {/* HUD Barra Superior */}
      <div className="flex justify-between items-start">
        <div className="bg-slate-900/60 border border-cyan-500/20 rounded px-4 py-2 backdrop-blur-md">
          <div className="text-[10px] font-mono tracking-[4px] text-cyan-400 font-bold uppercase">
            {ORB_STATE_HUD_LABELS[state] || "CEREBRO OPERATIVO"}
          </div>
          {status?.tasks?.message && (
            <div className="text-[11px] font-sans text-cyan-200/80 mt-1 max-w-sm leading-normal">
              {status.tasks.message}
            </div>
          )}
        </div>

        <div className="flex gap-2">
          <div className="bg-slate-900/60 border border-cyan-500/20 rounded px-3 py-1.5 backdrop-blur-md flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${wsConnected ? "bg-green-500 animate-pulse" : "bg-red-500"}`} />
            <span className="text-[10px] font-mono tracking-wider text-slate-300 font-medium">
              {wsConnected ? "CONEXIÓN DE EVENTOS ESTABLE" : "SISTEMA SIN CONEXIÓN"}
            </span>
          </div>
        </div>
      </div>

      {/* HUD Centro - Controles mínimos superpuestos */}
      <div className="self-center flex flex-col items-center gap-3">
        {/* Este espacio queda libre para el orbe 3D, colocamos los controles un poco abajo */}
      </div>

      {/* HUD Barra Inferior */}
      <div className="flex justify-between items-end">
        {/* Tareas en curso */}
        <div className="flex flex-col gap-2 max-w-md bg-slate-900/60 border border-cyan-500/10 rounded p-3 backdrop-blur-md">
          <div className="text-[9px] font-mono tracking-widest text-slate-400 font-bold uppercase">
            Cola de Tareas en ejecución
          </div>
          {activeSlow.length === 0 && activeFast.length === 0 ? (
            <div className="text-[11px] font-mono text-slate-400 italic">
              Ninguna tarea en ejecución activa
            </div>
          ) : (
            <div className="flex flex-col gap-1.5 mt-1">
              {activeSlow.map((t) => (
                <div key={t.task_id} className="text-[11px] font-mono text-amber-300 truncate max-w-xs">
                  ⚡ [Slow] {t.prompt}
                </div>
              ))}
              {activeFast.map((t) => (
                <div key={t.task_id} className="text-[11px] font-mono text-cyan-300 truncate max-w-xs">
                  ✨ [Fast] {t.prompt}
                </div>
              ))}
            </div>
          )}{pending.length > 0 && (
            <div className="text-[10px] font-mono text-green-400 mt-0.5">
              • {pending.length} tarea(s) en cola de espera
            </div>
          )}
        </div>

        {/* Acciones flotantes operativas directas */}
        <div className="flex gap-2 pointer-events-auto">
          <button
            onClick={handleMute}
            className="px-3.5 py-1.5 text-[11px] font-mono tracking-wider bg-slate-900/80 border border-cyan-500/20 hover:border-cyan-400/50 text-cyan-300 rounded hover:bg-cyan-950/20 transition backdrop-blur-md cursor-pointer"
          >
            MUTE MIC
          </button>
          <button
            onClick={handleWake}
            className="px-3.5 py-1.5 text-[11px] font-mono tracking-wider bg-slate-900/80 border border-cyan-500/20 hover:border-cyan-400/50 text-cyan-300 rounded hover:bg-cyan-950/20 transition backdrop-blur-md cursor-pointer"
          >
            {state === "dormant" ? "WAKE UP" : "SLEEP"}
          </button>
          {(activeSlow.length > 0 || state === "working_slow") && (
            <button
              onClick={handleCancel}
              className="px-3.5 py-1.5 text-[11px] font-mono tracking-wider bg-slate-900/85 border border-red-500/40 hover:border-red-400 text-red-300 rounded hover:bg-red-950/20 transition backdrop-blur-md cursor-pointer"
            >
              CANCEL TAREA
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
