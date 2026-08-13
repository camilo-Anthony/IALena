import React from "react";
import { useJarvisStore } from "../store/jarvisStore";
import { OrbScene } from "../components/orb/OrbScene";
import { OrbHUD } from "../components/orb/OrbHUD";

export function OrbView() {
  const orbState = useJarvisStore((s) => s.orbState);

  return (
    <div className="relative w-full h-full bg-transparent flex items-center justify-center pointer-events-none">
      {/* Three.js Orb Canvas en pantalla completa */}
      <div className="absolute inset-0 w-full h-full z-0">
        <OrbScene state={orbState} />
      </div>
    </div>
  );
}
