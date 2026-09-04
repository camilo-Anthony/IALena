import React, { useState } from "react";

interface CredentialsBudgetTabProps {
  formData: Record<string, string>;
  onInputChange: (key: string, value: string) => void;
  onSave: () => Promise<void>;
  isSaving: boolean;
  saveStatus: string | null;
}

export function CredentialsBudgetTab({
  formData,
  onInputChange,
  onSave,
  isSaving,
  saveStatus,
}: CredentialsBudgetTabProps) {
  const [newKeyInput, setNewKeyInput] = useState("");
  const [showMasterKey, setShowMasterKey] = useState(false);

  // Detectar claves existentes de Hermes
  const hermesKeyEntries = Object.keys(formData)
    .filter((k) => k.startsWith("HERMES_API_KEY_"))
    .sort((a, b) => {
      const numA = Number(a.replace("HERMES_API_KEY_", "")) || 0;
      const numB = Number(b.replace("HERMES_API_KEY_", "")) || 0;
      return numA - numB;
    });

  const dailyBudget = formData["DAILY_BUDGET"] || "5.0";
  const monthlyBudget = formData["MONTHLY_BUDGET"] || "50.0";

  const handleAddKeyToPool = () => {
    if (!newKeyInput.trim()) return;
    const nextIndex = hermesKeyEntries.length + 1;
    onInputChange(`HERMES_API_KEY_${nextIndex}`, newKeyInput.trim());
    setNewKeyInput("");
  };

  return (
    <div className="space-y-6">
      {/* ── SECCIÓN 1: CLAVE MAESTRA DE GEMINI ── */}
      <div className="bg-[#161618] border border-white/[0.08] rounded-2xl p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-white/[0.06]">
          <div>
            <div className="text-xs font-mono font-bold tracking-wider text-[#faf9f6] uppercase">
              Google Gemini Master API Key
            </div>
            <div className="text-[11px] text-[#868584] mt-0.5">
              Clave primaria de Google AI Studio utilizada para el socket de Gemini Live (Voz bidireccional).
            </div>
          </div>
          <span className="text-[10px] font-mono px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
            PRIMARIA
          </span>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between text-[11px] font-mono text-[#868584]">
            <span>GEMINI_API_KEY</span>
            <button
              type="button"
              onClick={() => setShowMasterKey(!showMasterKey)}
              className="text-cyan-400 hover:text-cyan-300 transition cursor-pointer"
            >
              {showMasterKey ? "Ocultar" : "Mostrar"}
            </button>
          </div>

          <input
            type={showMasterKey ? "text" : "password"}
            value={formData["GEMINI_API_KEY"] || ""}
            onChange={(e) => onInputChange("GEMINI_API_KEY", e.target.value)}
            placeholder="AIzaSy... o clave AQ..."
            className="w-full h-10 bg-[#111113] border border-white/[0.08] focus:border-cyan-500/50 rounded-xl px-3.5 text-xs font-mono text-[#faf9f6] outline-none transition"
          />
        </div>
      </div>

      {/* ── SECCIÓN 2: KEYROTATOR POOL (HERMES) ── */}
      <div className="bg-[#161618] border border-white/[0.08] rounded-2xl p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-white/[0.06]">
          <div>
            <div className="text-xs font-mono font-bold tracking-wider text-[#faf9f6] uppercase">
              Hermes KeyRotator Pool
            </div>
            <div className="text-[11px] text-[#868584] mt-0.5">
              Proxy local (127.0.0.1:8765) que rota Round-Robin entre múltiples cuentas para evitar límites 429.
            </div>
          </div>
          <span className="text-[10px] font-mono px-2.5 py-1 rounded-full bg-purple-500/10 text-purple-300 border border-purple-500/20">
            {hermesKeyEntries.length} CLAVES EN ROTACIÓN
          </span>
        </div>

        {/* Listado de Claves del Pool */}
        <div className="space-y-2.5">
          {hermesKeyEntries.map((keyName, idx) => {
            const rawVal = formData[keyName] || "";
            const masked =
              rawVal.length > 10
                ? `${rawVal.slice(0, 6)}...${rawVal.slice(-4)}`
                : "Configurada";

            return (
              <div
                key={keyName}
                className="p-3 bg-[#111113] border border-white/[0.05] rounded-xl flex items-center justify-between"
              >
                <div className="flex items-center gap-3">
                  <span className="w-2 h-2 rounded-full bg-purple-400" />
                  <div>
                    <span className="text-xs font-mono font-bold text-[#faf9f6]">
                      Slot {idx + 1} ({keyName})
                    </span>
                    <div className="text-[11px] font-mono text-[#868584]">{masked}</div>
                  </div>
                </div>

                <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                  ACTIVA
                </span>
              </div>
            );
          })}
        </div>

        {/* Input para Añadir Nueva Clave al Pool */}
        <div className="pt-3 border-t border-white/[0.06] space-y-2">
          <label className="block text-[11px] font-mono text-[#868584] uppercase">
            Añadir Nueva API Key al Pool de Hermes
          </label>
          <div className="flex gap-2">
            <input
              type="password"
              value={newKeyInput}
              onChange={(e) => setNewKeyInput(e.target.value)}
              placeholder="Pega aquí otra Gemini API Key (AIzaSy...)"
              className="flex-1 h-10 bg-[#111113] border border-white/[0.08] focus:border-purple-500/50 rounded-xl px-3.5 text-xs font-mono text-[#faf9f6] outline-none transition"
            />
            <button
              type="button"
              onClick={handleAddKeyToPool}
              disabled={!newKeyInput.trim()}
              className="px-4 py-2 bg-purple-600 hover:bg-purple-500 disabled:opacity-40 text-white text-xs font-mono font-medium rounded-xl transition cursor-pointer"
            >
              + Añadir Slot
            </button>
          </div>
        </div>
      </div>

      {/* ── SECCIÓN 3: PRESUPUESTOS & LÍMITES FINANCIEROS ── */}
      <div className="bg-[#161618] border border-white/[0.08] rounded-2xl p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-white/[0.06]">
          <div>
            <div className="text-xs font-mono font-bold tracking-wider text-[#faf9f6] uppercase">
              Presupuestos & Límites de Consumo (USD)
            </div>
            <div className="text-[11px] text-[#868584] mt-0.5">
              Topes de seguridad para evitar consumos inesperados en llamadas a APIs de pago.
            </div>
          </div>
          <span className="text-[10px] font-mono px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
            SAFETY LIMITS
          </span>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-[11px] font-mono text-[#868584] uppercase mb-1.5">
              Presupuesto Diario Máximo ($)
            </label>
            <input
              type="number"
              step="0.5"
              value={dailyBudget}
              onChange={(e) => onInputChange("DAILY_BUDGET", e.target.value)}
              placeholder="5.0"
              className="w-full h-10 bg-[#111113] border border-white/[0.08] focus:border-emerald-500/50 rounded-xl px-3.5 text-xs font-mono text-[#faf9f6] outline-none transition"
            />
          </div>

          <div>
            <label className="block text-[11px] font-mono text-[#868584] uppercase mb-1.5">
              Presupuesto Mensual Máximo ($)
            </label>
            <input
              type="number"
              step="5.0"
              value={monthlyBudget}
              onChange={(e) => onInputChange("MONTHLY_BUDGET", e.target.value)}
              placeholder="50.0"
              className="w-full h-10 bg-[#111113] border border-white/[0.08] focus:border-emerald-500/50 rounded-xl px-3.5 text-xs font-mono text-[#faf9f6] outline-none transition"
            />
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
          {isSaving ? "Guardando en .env..." : "Guardar Credenciales"}
        </button>
      </div>
    </div>
  );
}
