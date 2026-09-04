import React from "react";

const AVAILABLE_WAKE_MODELS = [
  { id: "tess", name: "Tess (Predeterminado)", desc: "Modelo local optimizado en español para activación instantánea.", badge: "Activo" },
  { id: "hey_jarvis", name: "Hey Jarvis", desc: "Clásico invocador de Jarvis en inglés/español." },
  { id: "alexa", name: "Alexa", desc: "Modelo universal openWakeWord de alta compatibilidad." },
  { id: "hey_mycroft", name: "Hey Mycroft", desc: "Modelo alternativo de código abierto." },
];

interface WakeWordConfigTabProps {
  formData: Record<string, string>;
  onInputChange: (key: string, value: string) => void;
  onSave: () => Promise<void>;
  isSaving: boolean;
  saveStatus: string | null;
}

export function WakeWordConfigTab({
  formData,
  onInputChange,
  onSave,
  isSaving,
  saveStatus,
}: WakeWordConfigTabProps) {
  const isWakeWordEnabled = formData["WAKE_WORD_ENABLED"] !== "0";
  const currentModel = formData["WAKE_WORD_MODEL"] || "tess";
  const threshold = Number(formData["WAKE_WORD_THRESHOLD"]) || 0.50;
  const frames = Number(formData["WAKE_WORD_CONSECUTIVE_FRAMES"]) || 2;
  const idleSleep = Number(formData["ACTIVATION_IDLE_SLEEP_SECONDS"]) || 30;

  return (
    <div className="space-y-6">
      {/* ── SECCIÓN 1: ESTADO MAESTRO DEL ACTIVADOR POR VOZ ── */}
      <div className="bg-[#161618] border border-white/[0.08] rounded-2xl p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-white/[0.06]">
          <div>
            <div className="text-xs font-mono font-bold tracking-wider text-[#faf9f6] uppercase">
              Activación por Palabra Mágica (Wake Word)
            </div>
            <div className="text-[11px] text-[#868584] mt-0.5">
              Detector acústico openWakeWord en tiempo real ejecutado 100% en local (sin conexión).
            </div>
          </div>
          <span
            className={`text-[10px] font-mono px-2.5 py-1 rounded-full border ${
              isWakeWordEnabled
                ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/20"
                : "bg-zinc-800 text-zinc-400 border-zinc-700"
            }`}
          >
            {isWakeWordEnabled ? "ACTIVADO" : "MODO ESCUCHA CONSTANTE"}
          </span>
        </div>

        {/* Interruptor Principal */}
        <div
          onClick={() => onInputChange("WAKE_WORD_ENABLED", isWakeWordEnabled ? "0" : "1")}
          className={`p-4 rounded-xl border transition cursor-pointer flex items-center justify-between ${
            isWakeWordEnabled
              ? "bg-emerald-500/10 border-emerald-500/30"
              : "bg-[#111113] border-white/[0.04] opacity-75"
          }`}
        >
          <div className="flex flex-col gap-0.5 pr-4">
            <span className="text-xs font-mono font-bold text-[#faf9f6]">
              Filtro de Palabra Mágica al Iniciar
            </span>
            <span className="text-[11px] text-[#868584]">
              Cuando está activo, JARVIS permanece en reposo y solo te responde cuando dices su nombre. Si lo apagas, escuchará siempre.
            </span>
          </div>
          <div
            className={`w-9 h-5 rounded-full p-0.5 shrink-0 transition-colors ${
              isWakeWordEnabled ? "bg-emerald-400" : "bg-white/[0.1]"
            }`}
          >
            <div
              className={`w-4 h-4 rounded-full bg-white transition-transform ${
                isWakeWordEnabled ? "translate-x-4" : "translate-x-0"
              }`}
            />
          </div>
        </div>

        {/* ── SELECTOR DE MODELO ACÚSTICO ── */}
        <div className="space-y-3 pt-3 border-t border-white/[0.04]">
          <span className="text-xs font-mono text-[#868584] uppercase block">
            Modelo de Activación Seleccionado
          </span>

          <div className="grid grid-cols-2 gap-3">
            {AVAILABLE_WAKE_MODELS.map((m) => {
              const isSelected = currentModel.toLowerCase() === m.id.toLowerCase();
              return (
                <div
                  key={m.id}
                  onClick={() => onInputChange("WAKE_WORD_MODEL", m.id)}
                  className={`p-3.5 rounded-xl border transition cursor-pointer flex flex-col justify-between gap-2 ${
                    isSelected
                      ? "bg-emerald-500/15 border-emerald-500/40 text-[#faf9f6]"
                      : "bg-[#111113] border-white/[0.04] text-[#afaeac] hover:border-white/[0.12]"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono font-bold text-[#faf9f6]">{m.name}</span>
                    <span className="text-xs font-mono text-emerald-400">
                      {isSelected ? "✓" : ""}
                    </span>
                  </div>
                  <p className="text-[10px] text-[#868584] leading-relaxed">{m.desc}</p>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* ── SECCIÓN 2: CALIBRACIÓN DE UMBRAL & SENSIBILIDAD ── */}
      <div className="bg-[#161618] border border-white/[0.08] rounded-2xl p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-white/[0.06]">
          <div>
            <div className="text-xs font-mono font-bold tracking-wider text-[#faf9f6] uppercase">
              Sensibilidad & Umbral Acústico
            </div>
            <div className="text-[11px] text-[#868584] mt-0.5">
              Ajusta la probabilidad necesaria para que la red neuronal active el Orbe.
            </div>
          </div>
          <span className="text-[10px] font-mono px-2.5 py-1 rounded-full bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
            NEURAL THRESHOLD
          </span>
        </div>

        <div className="grid grid-cols-2 gap-6">
          {/* Slider de Threshold */}
          <div className="space-y-2 bg-[#111113] p-4 rounded-xl border border-white/[0.04]">
            <div className="flex items-center justify-between text-xs font-mono">
              <span className="text-[#868584] uppercase">Umbral de Detección (Threshold)</span>
              <span className="text-[#faf9f6] font-bold">{(threshold * 100).toFixed(0)}% ({threshold.toFixed(2)})</span>
            </div>
            <input
              type="range"
              min="0.20"
              max="0.90"
              step="0.05"
              value={threshold}
              onChange={(e) => onInputChange("WAKE_WORD_THRESHOLD", e.target.value)}
              className="w-full accent-cyan-400 cursor-pointer"
            />
            <div className="flex justify-between text-[10px] font-mono text-[#868584]">
              <span>0.20 (Ultra Reactivo)</span>
              <span>0.60 (Óptimo)</span>
              <span>0.90 (Estricto)</span>
            </div>
          </div>

          {/* Frames Consecutivos */}
          <div className="space-y-2 bg-[#111113] p-4 rounded-xl border border-white/[0.04]">
            <div className="flex items-center justify-between text-xs font-mono">
              <span className="text-[#868584] uppercase">Frames Consecutivos Requeridos</span>
              <span className="text-[#faf9f6] font-bold">{frames} frames ({(frames * 80)}ms)</span>
            </div>
            <input
              type="range"
              min="1"
              max="5"
              step="1"
              value={frames}
              onChange={(e) => onInputChange("WAKE_WORD_CONSECUTIVE_FRAMES", e.target.value)}
              className="w-full accent-cyan-400 cursor-pointer"
            />
            <div className="flex justify-between text-[10px] font-mono text-[#868584]">
              <span>1 (Instantáneo)</span>
              <span>3 (Recomendado)</span>
              <span>5 (Anti-Ruidos)</span>
            </div>
          </div>
        </div>
      </div>

      {/* ── SECCIÓN 3: TIEMPO DE REPOSO (IDLE SLEEP) ── */}
      <div className="bg-[#161618] border border-white/[0.08] rounded-2xl p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-white/[0.06]">
          <div>
            <div className="text-xs font-mono font-bold tracking-wider text-[#faf9f6] uppercase">
              Tiempo de Reposo (Auto-Sleep Timer)
            </div>
            <div className="text-[11px] text-[#868584] mt-0.5">
              Cuántos segundos de silencio espera JARVIS tras hablar antes de volver a dormir.
            </div>
          </div>
          <span className="text-[10px] font-mono px-2.5 py-1 rounded-full bg-purple-500/10 text-purple-300 border border-purple-500/20">
            AUTO-SLEEP
          </span>
        </div>

        <div className="space-y-2 bg-[#111113] p-4 rounded-xl border border-white/[0.04]">
          <div className="flex items-center justify-between text-xs font-mono">
            <span className="text-[#868584] uppercase">Inactividad antes de Dormir (Idle Seconds)</span>
            <span className="text-[#faf9f6] font-bold">{idleSleep} segundos</span>
          </div>
          <input
            type="range"
            min="5"
            max="120"
            step="5"
            value={idleSleep}
            onChange={(e) => onInputChange("ACTIVATION_IDLE_SLEEP_SECONDS", e.target.value)}
            className="w-full accent-purple-400 cursor-pointer"
          />
          <div className="flex justify-between text-[10px] font-mono text-[#868584]">
            <span>5s (Duerme rápido)</span>
            <span>15s - 30s (Conversacional)</span>
            <span>120s (Permanece atento)</span>
          </div>
        </div>
      </div>

      {/* ── BARRA DE GUARDADO ── */}
      <div className="flex items-center justify-between pt-2">
        {saveStatus && (
          <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-3 py-1.5 rounded-lg">
            {saveStatus}
          </span>
        )}
        <button
          type="button"
          onClick={onSave}
          disabled={isSaving}
          className="ml-auto px-6 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-mono font-medium text-xs tracking-wider uppercase transition shadow-lg shadow-emerald-900/30 cursor-pointer disabled:opacity-50"
        >
          {isSaving ? "Guardando en .env..." : "Guardar Calibración de Wake Word"}
        </button>
      </div>
    </div>
  );
}
