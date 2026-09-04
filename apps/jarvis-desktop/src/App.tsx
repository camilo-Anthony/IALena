import React, { useEffect } from "react";
import { useJarvisStore } from "./store/jarvisStore";
import { useJarvisWS } from "./hooks/useJarvisWS";
import { jarvisAPI } from "./hooks/useJarvisAPI";
import { OrbView } from "./views/OrbView";
import { PanelView } from "./views/PanelView";

// Helper para invocar comandos de Tauri de forma segura y eficiente
async function invokeTauri(command: string, args: Record<string, unknown> = {}) {
  try {
    if (
      typeof window !== "undefined" &&
      ("__TAURI_INTERNALS__" in window || "__TAURI__" in window)
    ) {
      const { invoke } = await import("@tauri-apps/api/core");
      return await invoke(command, args);
    }
  } catch {
    // Ignorar en entorno de desarrollo web convencional
  }
}

export default function App() {
  const activeView = useJarvisStore((s) => s.activeView);
  const setStatus = useJarvisStore((s) => s.setStatus);
  const setConfig = useJarvisStore((s) => s.setConfig);
  const wsConnected = useJarvisStore((s) => s.wsConnected);

  // Iniciar la escucha del WebSocket de eventos en tiempo real
  useJarvisWS();

  // 1. Carga inicial y Polling Adaptativo (solo como respaldo cuando WebSocket esté desconectado)
  useEffect(() => {
    let isMounted = true;

    async function loadInitial() {
      try {
        const [statusData, configData] = await Promise.all([
          jarvisAPI.getStatus(),
          jarvisAPI.getConfig(),
        ]);
        if (isMounted) {
          setStatus(statusData);
          setConfig(configData);
        }
      } catch (e) {
        console.error("Error al cargar la info inicial de la API:", e);
      }
    }
    loadInitial();

    // Si WebSocket está conectado, reducimos el polling a un heartbeat pasivo (20s)
    // Si se desconecta, activamos polling frecuente de respaldo (4s)
    const pollIntervalMs = wsConnected ? 20000 : 4000;
    const timer = setInterval(async () => {
      try {
        const statusData = await jarvisAPI.getStatus();
        if (isMounted) setStatus(statusData);
      } catch {
        // Ignorar fallos temporales de red
      }
    }, pollIntervalMs);

    return () => {
      isMounted = false;
      clearInterval(timer);
    };
  }, [setStatus, setConfig, wsConnected]);

  // 2. Notificar a Tauri el cambio de vista para gestión de ventana y click-through
  useEffect(() => {
    invokeTauri("set_active_view_state", { view: activeView });
  }, [activeView]);

  // 3. Atajos de teclado globales para navegación rápida
  const setActiveView = useJarvisStore((s) => s.setActiveView);
  const setActivePanelTab = useJarvisStore((s) => s.setActivePanelTab);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Escape: volver al Orbe desde cualquier vista
      if (e.key === "Escape") {
        setActiveView("orb");
      }
      // Alt+1 / Ctrl+1: Orb
      if ((e.ctrlKey || e.altKey) && e.key === "1") {
        e.preventDefault();
        setActiveView("orb");
      }
      // Alt+2 / Ctrl+2: Panel Dashboard
      if ((e.ctrlKey || e.altKey) && e.key === "2") {
        e.preventDefault();
        setActivePanelTab("dashboard");
        setActiveView("panel");
      }
      // Alt+3 / Ctrl+3: Panel Hermes Cockpit
      if ((e.ctrlKey || e.altKey) && e.key === "3") {
        e.preventDefault();
        setActivePanelTab("hermes");
        setActiveView("panel");
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [setActiveView, setActivePanelTab]);

  return (
    <div className="w-screen h-screen overflow-hidden bg-transparent">
      {activeView === "orb" ? <OrbView /> : <PanelView />}
    </div>
  );
}
