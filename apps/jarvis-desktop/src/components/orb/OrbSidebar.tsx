import React, { useState, useEffect } from "react";
import { useJarvisStore } from "../../store/jarvisStore";
import { jarvisAPI } from "../../hooks/useJarvisAPI";
import type { OrbState } from "../../types";
import { ORB_COLORS, getOrbStateProfile } from "./orbColors";

interface OrbSidebarProps {
  state: OrbState;
}

export function OrbSidebar({ state }: OrbSidebarProps) {
  const [isOpen, setIsOpen] = useState(false);
  const setActiveView = useJarvisStore((s) => s.setActiveView);
  const wsConnected = useJarvisStore((s) => s.wsConnected);
  const status = useJarvisStore((s) => s.status);

  const profileKey = getOrbStateProfile(state);
  const color = ORB_COLORS[profileKey];

  // Notificar a Tauri cuando el menú se abre o se cierra
  useEffect(() => {
    async function notifySidebar() {
      try {
        if (
          typeof window !== "undefined" &&
          ("__TAURI_INTERNALS__" in window || "__TAURI__" in window)
        ) {
          const core = await import("@tauri-apps/api/core");
          await core.invoke("set_sidebar_open", { open: isOpen });
        }
      } catch {
        // Ignorar en web
      }
    }
    notifySidebar();
  }, [isOpen]);

  const handleMute = async () => {
    try { await jarvisAPI.toggleMute(); } catch (e) { console.error(e); }
  };

  const handleWake = async () => {
    try {
      if (state === "dormant") await jarvisAPI.wake();
      else await jarvisAPI.sleep();
    } catch (e) { console.error(e); }
  };

  const setActivePanelTab = useJarvisStore((s) => s.setActivePanelTab);

  const handleCancel = async () => {
    try { await jarvisAPI.cancelTask(); } catch (e) { console.error(e); }
  };

  const handleOpenHermes = () => {
    setIsOpen(false);
    setActivePanelTab("hermes");
    setActiveView("panel");
  };

  return (
    <>
      {/* ── BOTÓN DISPARADOR ANGULAR BISELADO (Tactical Chamfered Notch) ── */}
      <button
        onClick={() => setIsOpen(true)}
        className={`fixed right-0 top-1/2 -translate-y-1/2 z-20 pointer-events-auto cursor-pointer
          flex items-center justify-end transition-all duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] group
          ${isOpen ? "opacity-0 translate-x-8 pointer-events-none" : "opacity-100 translate-x-0"}`}
        title="JARVIS Menu"
      >
        <div
          className="relative flex items-center justify-center w-6 h-16 transition-all duration-300
            group-hover:w-8 backdrop-blur-xl shadow-2xl"
          style={{
            backgroundColor: "#0d0d10f0",
            // Corte chaflán angular a 45°: ni cuadrado ni curvo
            clipPath: "polygon(100% 0, 10px 0, 0 16px, 0 calc(100% - 16px), 10px 100%, 100% 100%)",
            boxShadow: `-4px 0 16px -2px ${color}35`,
          }}
        >
          {/* Borde biselado SVG perfectamente alineado con el chaflán */}
          <svg
            className="absolute inset-0 w-full h-full pointer-events-none"
            viewBox="0 0 100 100"
            preserveAspectRatio="none"
          >
            <polyline
              points="100,1 35,1 2,24 2,76 35,99 100,99"
              fill="none"
              stroke={color}
              strokeWidth="3"
              strokeOpacity="0.45"
              className="transition-all duration-300 group-hover:stroke-opacity-90"
            />
          </svg>

          {/* Micro-guía angular en el corte */}
          <div
            className="w-[2px] h-6 transition-all duration-300 opacity-60 group-hover:opacity-100 group-hover:h-8"
            style={{
              backgroundColor: color,
              boxShadow: `0 0 6px ${color}`,
            }}
          />
        </div>
      </button>

      {/* ── CARD FLOTANTE COMPACTA (Floating Command Flyout) ── */}
      <div
        className={`fixed right-6 top-1/2 -translate-y-1/2 w-[320px] z-30 pointer-events-auto
          flex flex-col rounded-2xl border transition-all duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] shadow-2xl p-6
          ${isOpen ? "translate-x-0 opacity-100 scale-100" : "translate-x-12 opacity-0 scale-95 pointer-events-none"}`}
        style={{
          backgroundColor: "#161618f5",
          borderColor: "rgba(255, 255, 255, 0.1)",
          backdropFilter: "blur(32px) saturate(1.3)",
          WebkitBackdropFilter: "blur(32px) saturate(1.3)",
        }}
      >
        {/* Header */}
        <div className="flex items-center justify-between pb-5 border-b border-white/[0.08]">
          <div className="flex items-center gap-3">
            <span className="w-2.5 h-2.5 rounded-full transition-colors duration-500" style={{ backgroundColor: color }} />
            <span className="text-xs font-mono font-semibold tracking-[2px] text-[#faf9f6] uppercase">JARVIS SYSTEM</span>
          </div>
          <button
            onClick={() => setIsOpen(false)}
            className="w-7 h-7 flex items-center justify-center rounded-full bg-[#242426] text-[#868584] hover:text-[#faf9f6] hover:bg-[#323235] transition cursor-pointer text-xs"
          >
            ✕
          </button>
        </div>

        {/* Telemetría Compacta en 2 Columnas */}
        <div className="grid grid-cols-2 gap-3 my-5">
          <div className="p-3.5 bg-[#1e1e22] border border-white/[0.05] rounded-xl flex flex-col gap-1.5">
            <span className="text-[9px] font-mono tracking-[1.5px] text-[#868584] uppercase">WAKE WORD</span>
            <div className="flex items-center gap-2">
              <span className={`w-1.5 h-1.5 rounded-full ${status?.wake_word?.wake_word_enabled !== false ? "bg-emerald-400" : "bg-[#868584]"}`} />
              <span className="text-xs font-mono font-medium text-[#faf9f6]">
                {status?.wake_word?.wake_word_enabled !== false ? "ARMED" : "MUTED"}
              </span>
            </div>
          </div>

          <div className="p-3.5 bg-[#1e1e22] border border-white/[0.05] rounded-xl flex flex-col gap-1.5">
            <span className="text-[9px] font-mono tracking-[1.5px] text-[#868584] uppercase">CORE LINK</span>
            <div className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full transition-colors duration-500" style={{ backgroundColor: wsConnected ? color : "#868584" }} />
              <span className="text-xs font-mono font-medium text-[#faf9f6]">
                {wsConnected ? "ONLINE" : "OFFLINE"}
              </span>
            </div>
          </div>
        </div>

        {/* Workspaces Navigation */}
        <div className="space-y-2.5 mb-5">
          <div className="text-[9px] font-mono tracking-[2px] text-[#868584] uppercase px-1">
            WORKSPACES
          </div>
          <div className="space-y-2">
            <button
              onClick={() => {
                setIsOpen(false);
                setActivePanelTab("dashboard");
                setActiveView("panel");
              }}
              className="w-full px-4 py-3 text-left text-[13px] text-[#afaeac] hover:text-[#faf9f6]
                bg-[#1e1e22] hover:bg-[#28282d] border border-white/[0.05] hover:border-white/[0.12]
                rounded-xl transition flex items-center justify-between cursor-pointer"
            >
              <span className="flex items-center gap-3">
                <span className="font-medium">Control Panel</span>
              </span>
              <span className="text-[10px] text-[#868584] font-mono bg-white/[0.04] px-2 py-0.5 rounded">Ctrl+2</span>
            </button>

            <button
              onClick={handleOpenHermes}
              className="w-full px-4 py-3 text-left text-[13px] text-[#afaeac] hover:text-[#faf9f6]
                bg-[#1e1e22] hover:bg-[#28282d] border border-white/[0.05] hover:border-white/[0.12]
                rounded-xl transition flex items-center justify-between cursor-pointer"
            >
              <span className="flex items-center gap-3">
                <span className="font-medium">Hermes Cockpit</span>
              </span>
              <span className="text-[10px] text-[#868584] font-mono bg-white/[0.04] px-2 py-0.5 rounded">Ctrl+3</span>
            </button>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="pt-4 border-t border-white/[0.08] space-y-3">
          <div className="text-[9px] font-mono tracking-[2px] text-[#868584] uppercase px-1">
            CONTROLS
          </div>

          <div className="grid grid-cols-2 gap-2.5">
            <button
              onClick={handleMute}
              className="px-3.5 py-2.5 text-center text-[13px] font-medium text-[#afaeac] hover:text-[#faf9f6]
                bg-[#242426] hover:bg-[#323235] border border-white/[0.06] rounded-full transition cursor-pointer"
            >
              Mic Toggle
            </button>

            <button
              onClick={handleWake}
              className="px-3.5 py-2.5 text-center text-[13px] font-medium text-[#afaeac] hover:text-[#faf9f6]
                bg-[#242426] hover:bg-[#323235] border border-white/[0.06] rounded-full transition cursor-pointer"
            >
              {state === "dormant" ? "Wake Up" : "Sleep"}
            </button>
          </div>

          <button
            onClick={handleCancel}
            className="w-full px-3.5 py-2.5 text-center text-[13px] font-medium text-red-400 hover:text-red-300
              bg-red-950/30 hover:bg-red-900/40 border border-red-500/20 rounded-full transition cursor-pointer"
          >
            Interrupt Active Task
          </button>
        </div>
      </div>
    </>
  );
}
