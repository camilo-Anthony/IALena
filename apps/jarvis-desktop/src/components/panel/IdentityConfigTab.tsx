import React from "react";

interface IdentityConfigTabProps {
  formData: Record<string, string>;
  onInputChange: (key: string, value: string) => void;
  onSave: () => Promise<void>;
  isSaving: boolean;
  saveStatus: string | null;
}

export function IdentityConfigTab({
  formData,
  onInputChange,
  onSave,
  isSaving,
  saveStatus,
}: IdentityConfigTabProps) {
  const assistantName = formData["ASSISTANT_NAME"] || "Tess";
  const userName = formData["USER_NAME"] || "Camilo";
  const language = formData["LANGUAGE"] || "es";
  const logLevel = formData["LOG_LEVEL"] || "INFO";
  const isMusicToolEnabled = formData["ENABLE_MUSIC_TOOL"] !== "0";

  return (
    <div className="space-y-6">
      {/* ── SECCIÓN 1: PERSONA & IDENTIDAD ── */}
      <div className="bg-[#161618] border border-white/[0.08] rounded-2xl p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-white/[0.06]">
          <div>
            <div className="text-xs font-mono font-bold tracking-wider text-[#faf9f6] uppercase">
              Identidad de Conversación & Usuario
            </div>
            <div className="text-[11px] text-[#868584] mt-0.5">
              Define el nombre con el que se identifica la IA y cómo se dirige a ti.
            </div>
          </div>
          <span className="text-[10px] font-mono px-2.5 py-1 rounded-full bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
            PERSONA
          </span>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-[11px] font-mono text-[#868584] uppercase mb-1.5">
              Nombre del Asistente
            </label>
            <input
              type="text"
              value={assistantName}
              onChange={(e) => onInputChange("ASSISTANT_NAME", e.target.value)}
              placeholder="Tess"
              className="w-full h-10 bg-[#111113] border border-white/[0.08] focus:border-cyan-500/50 rounded-xl px-3.5 text-xs font-mono text-[#faf9f6] outline-none transition"
            />
          </div>

          <div>
            <label className="block text-[11px] font-mono text-[#868584] uppercase mb-1.5">
              Tu Nombre (Usuario)
            </label>
            <input
              type="text"
              value={userName}
              onChange={(e) => onInputChange("USER_NAME", e.target.value)}
              placeholder="Camilo"
              className="w-full h-10 bg-[#111113] border border-white/[0.08] focus:border-cyan-500/50 rounded-xl px-3.5 text-xs font-mono text-[#faf9f6] outline-none transition"
            />
          </div>
        </div>
      </div>

      {/* ── SECCIÓN 2: IDIOMA & VERBOSIDAD DEL KERNEL ── */}
      <div className="bg-[#161618] border border-white/[0.08] rounded-2xl p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-white/[0.06]">
          <div>
            <div className="text-xs font-mono font-bold tracking-wider text-[#faf9f6] uppercase">
              Idioma & Registro de Diagnósticos
            </div>
            <div className="text-[11px] text-[#868584] mt-0.5">
              Localización de respuestas del sistema y nivel de detalle en terminal logs.
            </div>
          </div>
          <span className="text-[10px] font-mono px-2.5 py-1 rounded-full bg-purple-500/10 text-purple-300 border border-purple-500/20">
            SYSTEM CORE
          </span>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-[11px] font-mono text-[#868584] uppercase mb-1.5">
              Idioma Predeterminado
            </label>
            <div className="grid grid-cols-2 gap-2">
              {[
                { id: "es", label: "Español (es)" },
                { id: "en", label: "English (en)" },
              ].map((lang) => (
                <button
                  key={lang.id}
                  type="button"
                  onClick={() => onInputChange("LANGUAGE", lang.id)}
                  className={`py-2.5 rounded-xl border text-xs font-mono transition cursor-pointer ${
                    language.toLowerCase() === lang.id
                      ? "bg-purple-500/15 border-purple-500/40 text-purple-200 font-bold"
                      : "bg-[#111113] border-white/[0.04] text-[#868584] hover:text-[#faf9f6]"
                  }`}
                >
                  {lang.label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-[11px] font-mono text-[#868584] uppercase mb-1.5">
              Nivel de Log del Kernel
            </label>
            <div className="grid grid-cols-3 gap-2">
              {["DEBUG", "INFO", "WARNING"].map((lvl) => (
                <button
                  key={lvl}
                  type="button"
                  onClick={() => onInputChange("LOG_LEVEL", lvl)}
                  className={`py-2.5 rounded-xl border text-xs font-mono transition cursor-pointer ${
                    logLevel.toUpperCase() === lvl
                      ? "bg-purple-500/15 border-purple-500/40 text-purple-200 font-bold"
                      : "bg-[#111113] border-white/[0.04] text-[#868584] hover:text-[#faf9f6]"
                  }`}
                >
                  {lvl}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Feature Flags */}
        <div className="pt-3 border-t border-white/[0.04]">
          <div
            onClick={() => onInputChange("ENABLE_MUSIC_TOOL", isMusicToolEnabled ? "0" : "1")}
            className={`p-3.5 rounded-xl border transition cursor-pointer flex items-center justify-between ${
              isMusicToolEnabled
                ? "bg-purple-500/10 border-purple-500/30"
                : "bg-[#111113] border-white/[0.04] opacity-75"
            }`}
          >
            <div className="flex flex-col gap-0.5 pr-4">
              <span className="text-xs font-mono font-bold text-[#faf9f6]">
                Herramienta Directa de Música (YouTube/Streaming)
              </span>
              <span className="text-[10px] text-[#868584]">
                Permite a JARVIS reproducir pistas musicales al instante sin requerir delegación externa.
              </span>
            </div>
            <div
              className={`w-8 h-4.5 rounded-full p-0.5 shrink-0 transition-colors ${
                isMusicToolEnabled ? "bg-purple-400" : "bg-white/[0.1]"
              }`}
            >
              <div
                className={`w-3.5 h-3.5 rounded-full bg-white transition-transform ${
                  isMusicToolEnabled ? "translate-x-3.5" : "translate-x-0"
                }`}
              />
            </div>
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
          className="ml-auto px-6 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-mono font-medium text-xs tracking-wider uppercase transition shadow-lg shadow-purple-900/30 cursor-pointer disabled:opacity-50"
        >
          {isSaving ? "Guardando en .env..." : "Guardar Identidad"}
        </button>
      </div>
    </div>
  );
}
