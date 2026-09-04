import React from "react";
import { useJarvisStore } from "../store/jarvisStore";
import { OrbScene } from "../components/orb/OrbScene";
import { OrbHUD } from "../components/orb/OrbHUD";

export function OrbView() {
  const orbState = useJarvisStore((s) => s.orbState);

  return (
    <div className="fixed inset-0 w-screen h-screen bg-transparent overflow-hidden select-none pointer-events-none">
      {/* Canvas Three.js en Pantalla Completa: 100% Transparente */}
      <OrbScene state={orbState} />

      {/* Capa de HUD cuántico e interactivo */}
      <OrbHUD state={orbState} />
    </div>
  );
}
