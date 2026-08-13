import React, { useMemo } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import type { OrbState } from "../../types";
import { OrbSphere } from "./OrbSphere";
import { OrbRings } from "./OrbRings";
import { OrbSensors } from "./OrbSensors";

interface OrbSceneProps {
  state: OrbState;
}

export function OrbScene({ state }: OrbSceneProps) {
  // Configuración de visualización basada en el estado actual del orbe
  const config = useMemo(() => {
    switch (state) {
      case "listening":
        return {
          glowColor: "#00ff88",
          speed: 1.5,
          roughness: 0.1,
          scale: 1.1,
        };
      case "speaking":
        return {
          glowColor: "#00f5ff",
          speed: 2.5,
          roughness: 0.2,
          scale: 1.15,
        };
      case "thinking_fast":
        return {
          glowColor: "#ffd700",
          speed: 4.0,
          roughness: 0.4,
          scale: 1.05,
        };
      case "working_slow":
        return {
          glowColor: "#ff6b35",
          speed: 3.0,
          roughness: 0.5,
          scale: 1.1,
        };
      case "reconnecting":
      case "confirmation_pending":
        return {
          glowColor: "#7c3aed",
          speed: 2.0,
          roughness: 0.3,
          scale: 1.0,
        };
      case "error":
        return {
          glowColor: "#ff3366",
          speed: 5.0,
          roughness: 0.6,
          scale: 1.2,
        };
      case "dormant":
      default:
        return {
          glowColor: "#0066ff",
          speed: 0.3,
          roughness: 0.05,
          scale: 0.95,
        };
    }
  }, [state]);

  return (
    <Canvas
      camera={{ position: [0, 0, 5], fov: 60 }}
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        width: "100%",
        height: "100%",
        pointerEvents: "auto",
      }}
    >
      <ambientLight intensity={0.6} />
      <pointLight position={[10, 10, 10]} intensity={1.5} />
      <directionalLight position={[-5, 5, 5]} intensity={0.8} />

      {/* Esfera central con shader dinámico */}
      <OrbSphere stateName={state} />

      {/* Hebras / Sensores táctiles biológicos */}
      <OrbSensors color={config.glowColor} speed={config.speed} count={50} />

      {/* Anillos orbitales holográficos */}
      <OrbRings color={config.glowColor} speed={config.speed} />

      <OrbitControls
        enableZoom={false}
        enablePan={false}
        autoRotate
        autoRotateSpeed={0.5}
      />
    </Canvas>
  );
}
