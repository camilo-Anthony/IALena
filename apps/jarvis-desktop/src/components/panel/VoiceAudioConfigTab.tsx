import React, { useState } from "react";
import { jarvisAPI } from "../../hooks/useJarvisAPI";

export interface VoiceOption {
  id: string;
  name: string;
  gender: "Femenina" | "Masculina";
  tone: string;
  badge?: string;
}

export const AVAILABLE_VOICES: VoiceOption[] = [
  { id: "Aoede", name: "Aoede", gender: "Femenina", tone: "Brillante, dinámica y expresiva", badge: "Oficial" },
  { id: "Puck", name: "Puck", gender: "Masculina", tone: "Enérgica, amigable y veloz", badge: "Popular" },
  { id: "Charon", name: "Charon", gender: "Masculina", tone: "Grave, sobria y profesional", badge: "Calma" },
  { id: "Kore", name: "Kore", gender: "Femenina", tone: "Cálida, empática y relajada", badge: "Suave" },
  { id: "Fenrir", name: "Fenrir", gender: "Masculina", tone: "Profunda, resonante y autoritaria" },
  { id: "Leda", name: "Leda", gender: "Femenina", tone: "Nítida, juvenil y alegre" },
];

export const AVAILABLE_MODELS_LIVE = [
  { id: "gemini-3.1-flash-live-preview", name: "Gemini 3.1 Flash Live (Preview)", badge: "Recomendado" },
  { id: "gemini-2.5-flash-native-audio-preview-09-2025", name: "Gemini 2.5 Flash Native Audio", badge: "Ultra Baja Latencia" },
  { id: "gemini-2.0-flash-exp", name: "Gemini 2.0 Flash Experimental", badge: "Experimental" },
];

interface VoiceAudioConfigTabProps {
  formData: Record<string, string>;
  onInputChange: (key: string, value: string) => void;
  onSave: () => Promise<void>;
  isSaving: boolean;
  saveStatus: string | null;
}

export function VoiceAudioConfigTab({
  formData,
  onInputChange,
  onSave,
  isSaving,
  saveStatus,
}: VoiceAudioConfigTabProps) {
  const [isVoicePickerOpen, setIsVoicePickerOpen] = useState(false);
  const [isModelPickerOpen, setIsModelPickerOpen] = useState(false);

  const currentVoiceId = formData["VOICE_NAME"] || "Aoede";
  const matchedVoice = AVAILABLE_VOICES.find(
    (v) => v.id.toLowerCase() === currentVoiceId.toLowerCase()
  );

  const currentModelId = formData["MODEL_LIVE"] || "gemini-3.1-flash-live-preview";
  const matchedModel = AVAILABLE_MODELS_LIVE.find(
    (m) => m.id.toLowerCase() === currentModelId.toLowerCase()
  );

  const silenceMs = Number(formData["LIVE_VAD_SILENCE_DURATION_MS"]) || 300;
  const paddingMs = Number(formData["LIVE_VAD_PREFIX_PADDING_MS"]) || 100;
  const micGain = Number(formData["MIC_GAIN"]) || 3.5;
  const isNoiseGateEnabled = formData["MIC_NOISE_GATE_ENABLED"] === "1";

  return (
    <div className="space-y-6">
      {/* ── SECCIÓN 1: MOTOR MULTIMODAL & MODELO LIVE ── */}
      <div className="bg-[#161618] border border-white/[0.08] rounded-2xl p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-white/[0.06]">
          <div>
            <div className="text-xs font-mono font-bold tracking-wider text-[#faf9f6] uppercase">
              Motor de Voz Gemini Live
            </div>
            <div className="text-[11px] text-[#868584] mt-0.5">
              Protocolo WebSocket bidireccional de baja latencia con audio nativo PCM a 24kHz.
            </div>
          </div>
          <span className="text-[10px] font-mono px-2.5 py-1 rounded-full bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
            MULTIMODAL API
          </span>
        </div>

        {/* Selector de Modelo Live */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono text-[#868584] uppercase">Modelo Multimodal Activo</span>
            <button
              type="button"
              onClick={() => setIsModelPickerOpen(!isModelPickerOpen)}
              className="text-xs font-mono text-cyan-400 hover:text-cyan-300 cursor-pointer"
            >
              {isModelPickerOpen ? "Cerrar lista" : "Cambiar modelo"}
            </button>
          </div>

          <div
            onClick={() => setIsModelPickerOpen(!isModelPickerOpen)}
            className="w-full p-3.5 bg-[#111113] hover:bg-[#141416] border border-white/[0.08] rounded-xl flex items-center justify-between transition cursor-pointer"
          >
            <div className="flex items-center gap-3">
              <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 shadow-[0_0_8px_#22d3ee]" />
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono font-bold text-[#faf9f6]">
                    {matchedModel ? matchedModel.name : currentModelId}
                  </span>
                  {matchedModel?.badge && (
                    <span className="text-[9px] font-mono px-2 py-0.5 rounded bg-cyan-500/15 text-cyan-300 border border-cyan-500/30">
                      {matchedModel.badge}
                    </span>
                  )}
                </div>
                <div className="text-[10px] font-mono text-[#868584] mt-0.5">
                  ID: {currentModelId}
                </div>
              </div>
            </div>
            <span className="text-xs font-mono text-[#868584]">{isModelPickerOpen ? "▲" : "▼"}</span>
          </div>

          {isModelPickerOpen && (
            <div className="p-3 bg-[#111113] border border-white/[0.08] rounded-xl space-y-2 animate-fade-in">
              {AVAILABLE_MODELS_LIVE.map((m) => (
                <div
                  key={m.id}
                  onClick={() => {
                    onInputChange("MODEL_LIVE", m.id);
                    setIsModelPickerOpen(false);
                  }}
                  className={`p-3 rounded-lg border transition cursor-pointer flex items-center justify-between ${
                    currentModelId.toLowerCase() === m.id.toLowerCase()
                      ? "bg-cyan-500/15 border-cyan-500/40 text-[#faf9f6]"
                      : "bg-[#161619] border-white/[0.04] text-[#afaeac] hover:border-white/[0.12]"
                  }`}
                >
                  <div className="flex flex-col gap-0.5">
                    <span className="text-xs font-mono font-bold text-[#faf9f6]">{m.name}</span>
                    <span className="text-[10px] font-mono text-[#868584]">{m.id}</span>
                  </div>
                  {m.badge && (
                    <span className="text-[9px] font-mono px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
                      {m.badge}
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ── CATÁLOGO DE VOCES DE GEMINI LIVE ── */}
        <div className="pt-4 border-t border-white/[0.06] space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-xs font-mono text-[#868584] uppercase block">
                Voz Sintetizada de Respuesta
              </span>
              <span className="text-[11px] text-[#868584]">
                Tono acústico y timbre con el que JARVIS responde en vivo.
              </span>
            </div>

            <button
              type="button"
              onClick={() => setIsVoicePickerOpen(!isVoicePickerOpen)}
              className="px-3 py-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-xs font-mono text-cyan-300 hover:text-cyan-200 transition cursor-pointer flex items-center gap-2"
            >
              <span>{isVoicePickerOpen ? "Ocultar Catálogo" : "Ver Catálogo Completo"}</span>
              <span className="text-[10px]">{isVoicePickerOpen ? "▲" : "▼"}</span>
            </button>
          </div>

          {/* Tarjeta de voz activa */}
          <div
            onClick={() => setIsVoicePickerOpen(!isVoicePickerOpen)}
            className="w-full p-3.5 bg-[#111113] hover:bg-[#141416] border border-white/[0.08] rounded-xl flex items-center justify-between transition cursor-pointer"
          >
            <div className="flex items-center gap-3">
              <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 shadow-[0_0_8px_#22d3ee]" />
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono font-bold text-[#faf9f6]">
                    {matchedVoice ? matchedVoice.name : currentVoiceId}
                  </span>
                  {matchedVoice && (
                    <span
                      className={`text-[9px] font-mono px-2 py-0.5 rounded ${
                        matchedVoice.gender === "Femenina"
                          ? "bg-pink-950/40 text-pink-300 border border-pink-500/20"
                          : "bg-blue-950/40 text-blue-300 border border-blue-500/20"
                      }`}
                    >
                      {matchedVoice.gender}
                    </span>
                  )}
                </div>
                <div className="text-[11px] text-[#868584] mt-0.5">
                  {matchedVoice ? matchedVoice.tone : "Voz ingresada manualmente"}
                </div>
              </div>
            </div>
            <span className="text-xs font-mono text-[#868584]">{isVoicePickerOpen ? "▲" : "▼"}</span>
          </div>

          {/* Grilla Desplegable de Voces */}
          {isVoicePickerOpen && (
            <div className="p-4 bg-[#111113] border border-white/[0.08] rounded-xl space-y-3 animate-fade-in">
              <div className="grid grid-cols-2 gap-2.5">
                {AVAILABLE_VOICES.map((v) => {
                  const isSelected = currentVoiceId.toLowerCase() === v.id.toLowerCase();
                  return (
                    <div
                      key={v.id}
                      onClick={() => onInputChange("VOICE_NAME", v.id)}
                      className={`p-3 rounded-xl border transition cursor-pointer flex items-center justify-between ${
                        isSelected
                          ? "bg-cyan-500/15 border-cyan-500/40 text-[#faf9f6]"
                          : "bg-[#161619] border-white/[0.04] text-[#afaeac] hover:border-white/[0.12]"
                      }`}
                    >
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-mono font-bold text-[#faf9f6]">{v.name}</span>
                          <span
                            className={`text-[9px] font-mono px-1.5 py-0.5 rounded ${
                              v.gender === "Femenina"
                                ? "bg-pink-950/40 text-pink-300 border border-pink-500/20"
                                : "bg-blue-950/40 text-blue-300 border border-blue-500/20"
                            }`}
                          >
                            {v.gender}
                          </span>
                        </div>
                        <div className="text-[10px] text-[#868584] leading-tight">{v.tone}</div>
                      </div>
                      <span className="text-xs font-mono text-cyan-400 pl-2">{isSelected ? "✓" : ""}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── SECCIÓN 2: CALIBRACIÓN DE MICRÓFONO & AUDIO ── */}
      <div className="bg-[#161618] border border-white/[0.08] rounded-2xl p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-white/[0.06]">
          <div>
            <div className="text-xs font-mono font-bold tracking-wider text-[#faf9f6] uppercase">
              Calibración de Micrófono & Filtros
            </div>
            <div className="text-[11px] text-[#868584] mt-0.5">
              Ganancia digital por software y compresión de ruido de fondo.
            </div>
          </div>
          <span className="text-[10px] font-mono px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
            AUDIO INPUT
          </span>
        </div>

        <div className="grid grid-cols-2 gap-6">
          {/* Ganancia del micrófono */}
          <div className="space-y-2 bg-[#111113] p-4 rounded-xl border border-white/[0.04]">
            <div className="flex items-center justify-between text-xs font-mono">
              <span className="text-[#868584] uppercase">Ganancia Digital (Mic Gain)</span>
              <span className="text-[#faf9f6] font-bold">{micGain.toFixed(1)}x</span>
            </div>
            <input
              type="range"
              min="1.0"
              max="6.0"
              step="0.1"
              value={micGain}
              onChange={(e) => onInputChange("MIC_GAIN", e.target.value)}
              className="w-full accent-cyan-400 cursor-pointer"
            />
            <div className="flex justify-between text-[10px] font-mono text-[#868584]">
              <span>1.0x (Normal)</span>
              <span>3.5x (Recomendado)</span>
              <span>6.0x (Sensible)</span>
            </div>
          </div>

          {/* Noise Gate Switch */}
          <div
            onClick={() => onInputChange("MIC_NOISE_GATE_ENABLED", isNoiseGateEnabled ? "0" : "1")}
            className={`p-4 rounded-xl border transition cursor-pointer flex items-center justify-between ${
              isNoiseGateEnabled
                ? "bg-cyan-500/10 border-cyan-500/30"
                : "bg-[#111113] border-white/[0.04] opacity-75"
            }`}
          >
            <div className="flex flex-col gap-0.5 pr-3">
              <span className="text-xs font-mono font-bold text-[#faf9f6]">
                Noise Gate por Software
              </span>
              <span className="text-[10px] text-[#868584]">
                Corta automáticamente ruidos mecánicos de fondo leves (ventiladores, teclado).
              </span>
            </div>
            <div
              className={`w-8 h-4.5 rounded-full p-0.5 shrink-0 transition-colors ${
                isNoiseGateEnabled ? "bg-cyan-400" : "bg-white/[0.1]"
              }`}
            >
              <div
                className={`w-3.5 h-3.5 rounded-full bg-white transition-transform ${
                  isNoiseGateEnabled ? "translate-x-3.5" : "translate-x-0"
                }`}
              />
            </div>
          </div>
        </div>
      </div>

      {/* ── SECCIÓN 3: LATENCIA Y DETECCIÓN DE ACTIVIDAD DE VOZ (VAD) ── */}
      <div className="bg-[#161618] border border-white/[0.08] rounded-2xl p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-white/[0.06]">
          <div>
            <div className="text-xs font-mono font-bold tracking-wider text-[#faf9f6] uppercase">
              VAD (Voice Activity Detector) & Latencia
            </div>
            <div className="text-[11px] text-[#868584] mt-0.5">
              Controla la velocidad con la que JARVIS detecta que terminaste de hablar.
            </div>
          </div>
          <span className="text-[10px] font-mono px-2.5 py-1 rounded-full bg-purple-500/10 text-purple-300 border border-purple-500/20">
            ULTRA-LOW LATENCY
          </span>
        </div>

        <div className="grid grid-cols-2 gap-6">
          {/* Silencio para corte */}
          <div className="space-y-2 bg-[#111113] p-4 rounded-xl border border-white/[0.04]">
            <div className="flex items-center justify-between text-xs font-mono">
              <span className="text-[#868584] uppercase">Silencio de Corte (End Silence)</span>
              <span className="text-[#faf9f6] font-bold">{silenceMs} ms</span>
            </div>
            <input
              type="range"
              min="150"
              max="800"
              step="25"
              value={silenceMs}
              onChange={(e) => onInputChange("LIVE_VAD_SILENCE_DURATION_MS", e.target.value)}
              className="w-full accent-purple-400 cursor-pointer"
            />
            <div className="flex justify-between text-[10px] font-mono text-[#868584]">
              <span>150ms (Ultra Rápido)</span>
              <span>300ms (Natural)</span>
              <span>800ms (Pausado)</span>
            </div>
          </div>

          {/* Padding de prefijo */}
          <div className="space-y-2 bg-[#111113] p-4 rounded-xl border border-white/[0.04]">
            <div className="flex items-center justify-between text-xs font-mono">
              <span className="text-[#868584] uppercase">Prefix Padding (Pre-Roll)</span>
              <span className="text-[#faf9f6] font-bold">{paddingMs} ms</span>
            </div>
            <input
              type="range"
              min="50"
              max="300"
              step="25"
              value={paddingMs}
              onChange={(e) => onInputChange("LIVE_VAD_PREFIX_PADDING_MS", e.target.value)}
              className="w-full accent-purple-400 cursor-pointer"
            />
            <div className="flex justify-between text-[10px] font-mono text-[#868584]">
              <span>50ms</span>
              <span>100ms (Óptimo)</span>
              <span>300ms</span>
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
          className="ml-auto px-6 py-2.5 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white font-mono font-medium text-xs tracking-wider uppercase transition shadow-lg shadow-cyan-900/30 cursor-pointer disabled:opacity-50"
        >
          {isSaving ? "Guardando en .env..." : "Guardar Ajustes de Audio"}
        </button>
      </div>
    </div>
  );
}
