import React, { useEffect } from "react";
import { useJarvisStore } from "./store/jarvisStore";
import { useJarvisWS } from "./hooks/useJarvisWS";
import { jarvisAPI } from "./hooks/useJarvisAPI";
import { OrbView } from "./views/OrbView";
import { PanelView } from "./views/PanelView";
import { HermesView } from "./views/HermesView";

export default function App() {
  const activeView = useJarvisStore((s) => s.activeView);
  const setActiveView = useJarvisStore((s) => s.setActiveView);
  const setStatus = useJarvisStore((s) => s.setStatus);
  const setConfig = useJarvisStore((s) => s.setConfig);

  // Iniciar la escucha del WebSocket de eventos en tiempo real
  useJarvisWS();

  // Polling y carga inicial de status y config
  useEffect(() => {
    async function loadInitial() {
      try {
        const [statusData, configData] = await Promise.all([
          jarvisAPI.getStatus(),
          jarvisAPI.getConfig(),
        ]);
        setStatus(statusData);
        setConfig(configData);
      } catch (e) {
        console.error("Error al cargar la info inicial de la API:", e);
      }
    }
    loadInitial();

    // Mantener sincronizado el estado básico mediante polling cada 4 segundos
    const t = setInterval(async () => {
      try {
        const statusData = await jarvisAPI.getStatus();
        setStatus(statusData);
      } catch (e) {
        // Ignorar fallos de red temporales
      }
    }, 4000);

    return () => clearInterval(t);
  }, [setStatus, setConfig]);

  return (
    <div className={`w-screen h-screen flex flex-col overflow-hidden text-[#e0f4ff] font-sans select-none relative ${activeView === "orb" ? "bg-transparent" : "bg-[#020408]"}`}>
      
      {/* HUD Cabecera Global de Navegación (Auto-hide si estamos en el Orbe para el efecto transparente) */}
      <header 
        className={`absolute top-0 inset-x-0 h-12 border-b border-cyan-500/20 bg-slate-950/80 px-5 flex items-center justify-between z-50 shrink-0 transition-opacity duration-300 ${
          activeView === "orb" ? "opacity-0 hover:opacity-100" : "opacity-100 relative"
        }`}
      >
        <div className="flex items-center gap-2 cursor-pointer" onClick={() => setActiveView("orb")}>
          <div className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-ping" />
          <span className="font-mono text-sm tracking-[5px] text-cyan-300 font-bold">JARVIS</span>
        </div>

        {/* Botones de navegación de vistas principales */}
        <div className="flex gap-2">
          <button
            onClick={() => setActiveView("orb")}
            className={`px-4 py-1 text-xs font-mono tracking-widest rounded border transition cursor-pointer ${
              activeView === "orb"
                ? "bg-cyan-500/10 border-cyan-500/50 text-cyan-300 font-bold"
                : "border-transparent text-slate-400 hover:text-cyan-400"
            }`}
          >
            ORBE
          </button>
          <button
            onClick={() => setActiveView("panel")}
            className={`px-4 py-1 text-xs font-mono tracking-widest rounded border transition cursor-pointer ${
              activeView === "panel"
                ? "bg-cyan-500/10 border-cyan-500/50 text-cyan-300 font-bold"
                : "border-transparent text-slate-400 hover:text-cyan-400"
            }`}
          >
            PANEL
          </button>
          <button
            onClick={() => setActiveView("hermes")}
            className={`px-4 py-1 text-xs font-mono tracking-widest rounded border transition cursor-pointer ${
              activeView === "hermes"
                ? "bg-cyan-500/10 border-cyan-500/50 text-cyan-300 font-bold"
                : "border-transparent text-slate-400 hover:text-cyan-400"
            }`}
          >
            HERMES
          </button>
        </div>
      </header>

      {/* Contenedor principal de Vistas con destrucción condicional */}
      <main className="flex-1 min-h-0 relative z-10 w-full h-full pointer-events-none">
        <div className="pointer-events-auto w-full h-full p-4">
          {activeView === "orb" && <OrbView />}
          {activeView === "panel" && <PanelView />}
          {activeView === "hermes" && <HermesView />}
        </div>
      </main>
    </div>
  );
}
