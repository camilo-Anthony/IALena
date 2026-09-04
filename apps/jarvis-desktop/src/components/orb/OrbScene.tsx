import React, { useRef, useMemo, useState, useCallback, useEffect } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import type { OrbState } from "../../types";

import { OrbCore } from "./OrbCore";
import { OrbParticleCloud } from "./OrbParticleCloud";
import { OrbSynapses } from "./OrbSynapses";
import { OrbOrbits } from "./OrbOrbits";
import { OrbFilaments } from "./OrbFilaments";
import { OrbSparks } from "./OrbSparks";
import { ORB_COLORS, getOrbStateProfile } from "./orbColors";

// ── DEFINICIÓN DE PERFILES VISUALES POR ESTADO ─────────────────────────────
interface StateVisualConfig {
  name: string;
  color: THREE.Color;
  scaleMult: number;
  rotSpeed: number;
  synapseDensity: number;
  orbitSpeedMult: number;
  vibration: number;
  extMotion: number;
}

const STATE_CONFIGS: Record<string, StateVisualConfig> = {
  reposo: {
    name: "REPOSO",
    color: new THREE.Color(ORB_COLORS.reposo),
    scaleMult: 1.0,
    rotSpeed: 0.008,
    synapseDensity: 0.2,
    orbitSpeedMult: 0.6,
    vibration: 0.0,
    extMotion: 0.25,
  },
  escuchando: {
    name: "ESCUCHANDO",
    color: new THREE.Color(ORB_COLORS.escuchando),
    scaleMult: 0.90,
    rotSpeed: 0.025,
    synapseDensity: 0.6,
    orbitSpeedMult: 1.3,
    vibration: 0.8,
    extMotion: 0.8,
  },
  pensando: {
    name: "PENSANDO",
    color: new THREE.Color(ORB_COLORS.pensando),
    scaleMult: 1.06,
    rotSpeed: 0.05,
    synapseDensity: 1.0,
    orbitSpeedMult: 1.8,
    vibration: 0.3,
    extMotion: 0.15,
  },
  hablando: {
    name: "HABLANDO",
    color: new THREE.Color(ORB_COLORS.hablando),
    scaleMult: 1.05,
    rotSpeed: 0.02,
    synapseDensity: 0.7,
    orbitSpeedMult: 1.2,
    vibration: 0.5,
    extMotion: 0.7,
  },
  ejecutando: {
    name: "EJECUTANDO",
    color: new THREE.Color(ORB_COLORS.ejecutando),
    scaleMult: 1.15,
    rotSpeed: 0.09,
    synapseDensity: 0.9,
    orbitSpeedMult: 2.8,
    vibration: 1.2,
    extMotion: 1.2,
  },
};

const mapOrbStateToProfile = getOrbStateProfile;

// Escala reducida en un 10%
const COMPACT_SCALE = 0.40;

// ── CONTENEDOR 3D DEL ORBE CON FÍSICA MAGNÉTICA POR TODA LA PANTALLA ───────
interface OrbContentProps {
  state: OrbState;
}

function OrbContent({ state }: OrbContentProps) {
  const groupRef = useRef<THREE.Group>(null);
  const coreGroupRef = useRef<THREE.Group>(null);
  const { viewport } = useThree();

  const profileKey = useMemo(() => mapOrbStateToProfile(state), [state]);
  const currentCfg = STATE_CONFIGS[profileKey] || STATE_CONFIGS.reposo;

  const activeColor = useRef(new THREE.Color().copy(currentCfg.color));
  const targetColor = useRef(new THREE.Color().copy(currentCfg.color));

  const [cloudPositions, setCloudPositions] = useState<Float32Array | null>(null);

  const handlePositionsReady = useCallback((pos: Float32Array) => {
    setCloudPositions(pos);
  }, []);

  // Variables de dinámica interna con interpolación continua suave (sin saltos bruscos)
  const smoothScaleMult = useRef(currentCfg.scaleMult);
  const smoothRotSpeed = useRef(currentCfg.rotSpeed);
  const smoothSynapseDensity = useRef(currentCfg.synapseDensity);
  const smoothOrbitSpeedMult = useRef(currentCfg.orbitSpeedMult);
  const smoothVibration = useRef(currentCfg.vibration);
  const smoothExtMotion = useRef(currentCfg.extMotion);
  const smoothCloudFocus = useRef(1.0);

  const tiltCurrent = useRef(0);
  const coreDisplace = useRef(0);
  const compressVal = useRef(1.0);
  const simAudio = useRef(0);
  const filSpeedFactor = useRef(1.0);

  // Física magnética (polos iguales) y posición en pantalla
  const orbPos = useRef(new THREE.Vector2(0, 0));
  const orbVel = useRef(new THREE.Vector2(0, 0));
  const evasionTilt = useRef(new THREE.Vector2(0, 0));
  const pointer3d = useRef(new THREE.Vector2(9999, 9999));

  // Rastreo continuo del cursor nativo de Windows (compatible con click-through total)
  useEffect(() => {
    const isTauri =
      typeof window !== "undefined" &&
      ("__TAURI_INTERNALS__" in window || "__TAURI__" in window);

    let active = true;

    if (isTauri) {
      import("@tauri-apps/api/core")
        .then((core) => {
          const poll = async () => {
            if (!active) return;
            try {
              const pos: [number, number] | null = await core.invoke("get_cursor_position");
              if (pos && Array.isArray(pos) && pos.length === 2) {
                const [px, py] = pos;
                const dpr = window.devicePixelRatio || 1;
                const screenW = (window.innerWidth || 1920) * dpr;
                const screenH = (window.innerHeight || 1080) * dpr;
                const ndcX = Math.max(-1, Math.min(1, (px / screenW) * 2 - 1));
                const ndcY = Math.max(-1, Math.min(1, -((py / screenH) * 2 - 1)));
                pointer3d.current.set(
                  (ndcX * viewport.width) / 2,
                  (ndcY * viewport.height) / 2
                );
              }
            } catch {
              // Fallback silencioso
            }
            if (active) setTimeout(poll, 16);
          };
          poll();
        })
        .catch(() => {});
    } else {
      const handleMouseMove = (e: MouseEvent) => {
        const ndcX = Math.max(-1, Math.min(1, (e.clientX / window.innerWidth) * 2 - 1));
        const ndcY = Math.max(-1, Math.min(1, -((e.clientY / window.innerHeight) * 2 - 1)));
        pointer3d.current.set(
          (ndcX * viewport.width) / 2,
          (ndcY * viewport.height) / 2
        );
      };

      window.addEventListener("mousemove", handleMouseMove, { passive: true });
      return () => {
        active = false;
        window.removeEventListener("mousemove", handleMouseMove);
      };
    }

    return () => {
      active = false;
    };
  }, [viewport]);

  useFrame((rState, delta) => {
    const time = rState.clock.getElapsedTime();
    targetColor.current.copy(currentCfg.color);

    // Transición suave y orgánica de color independiente de fps
    const colorBlend = 1 - Math.exp(-delta * 6.0);
    activeColor.current.lerp(targetColor.current, colorBlend);

    // Suavizado continuo de todas las métricas de estado
    smoothScaleMult.current += (currentCfg.scaleMult - smoothScaleMult.current) * (1 - Math.exp(-delta * 2.8));
    smoothRotSpeed.current += (currentCfg.rotSpeed - smoothRotSpeed.current) * (1 - Math.exp(-delta * 2.5));
    smoothSynapseDensity.current += (currentCfg.synapseDensity - smoothSynapseDensity.current) * (1 - Math.exp(-delta * 2.5));
    smoothOrbitSpeedMult.current += (currentCfg.orbitSpeedMult - smoothOrbitSpeedMult.current) * (1 - Math.exp(-delta * 2.5));
    smoothVibration.current += (currentCfg.vibration - smoothVibration.current) * (1 - Math.exp(-delta * 3.2));
    smoothExtMotion.current += (currentCfg.extMotion - smoothExtMotion.current) * (1 - Math.exp(-delta * 2.5));

    const targetCloudFocus = profileKey === "escuchando" ? 0.88 : 1.0;
    smoothCloudFocus.current += (targetCloudFocus - smoothCloudFocus.current) * (1 - Math.exp(-delta * 2.5));

    // Audio simulado sutil si está en modo de escucha o habla
    if (profileKey === "hablando" || profileKey === "escuchando") {
      simAudio.current += (Math.random() - simAudio.current) * 0.14;
      if (simAudio.current < 0.06) simAudio.current = 0.06;
    } else {
      simAudio.current += (0 - simAudio.current) * (1 - Math.exp(-delta * 3.0));
    }

    const effectiveAudio = simAudio.current * (profileKey === "hablando" ? 2.4 : 1.3);

    // Respiración biológica armónica
    const organicBreath = 1.0 + 0.015 * (Math.sin(time * 0.8) + 0.5 * Math.sin(time * 1.9));

    // Compresión en modo escucha con interpolación amortiguada
    const compressGoal = profileKey === "escuchando" ? 0.90 : 1.0;
    compressVal.current += (compressGoal - compressVal.current) * (1 - Math.exp(-delta * 2.5));

    const totalScale =
      COMPACT_SCALE *
      organicBreath *
      smoothScaleMult.current *
      compressVal.current *
      (1.0 + effectiveAudio * 0.15);

    // ── FÍSICA DE REPULSIÓN MAGNÉTICA & RETORNO ELÁSTICO AL CENTRO ──
    const pointerX = pointer3d.current.x;
    const pointerY = pointer3d.current.y;

    // Límites de la pantalla completa del monitor (rincones y bordes)
    const margin = 0.8;
    const boundX = Math.max(1.0, viewport.width / 2 - margin);
    const boundY = Math.max(1.0, viewport.height / 2 - margin);

    // Distancia al cursor para repulsión magnética
    const fromPointerX = orbPos.current.x - pointerX;
    const fromPointerY = orbPos.current.y - pointerY;
    const distToPointer = Math.sqrt(fromPointerX * fromPointerX + fromPointerY * fromPointerY);

    const MAGNETIC_REPEL_RADIUS = 3.5;

    if (distToPointer < MAGNETIC_REPEL_RADIUS && distToPointer > 0.01) {
      // Fuerza de repulsión reactiva y ágil
      const pushStrength = Math.pow((MAGNETIC_REPEL_RADIUS - distToPointer) / MAGNETIC_REPEL_RADIUS, 1.3) * 16.0;
      const normX = fromPointerX / distToPointer;
      const normY = fromPointerY / distToPointer;

      // El puntero empuja magnéticamente al orbe
      orbVel.current.x += normX * pushStrength * delta;
      orbVel.current.y += normY * pushStrength * delta;

      // Inclinación 3D reactiva alejándose del empuje
      evasionTilt.current.x += ((-normY * 0.28) - evasionTilt.current.x) * (1 - Math.exp(-delta * 6.0));
      evasionTilt.current.y += ((normX * 0.28) - evasionTilt.current.y) * (1 - Math.exp(-delta * 6.0));
    } else {
      // Retorno suave de la inclinación a 0
      evasionTilt.current.x += (0 - evasionTilt.current.x) * (1 - Math.exp(-delta * 3.0));
      evasionTilt.current.y += (0 - evasionTilt.current.y) * (1 - Math.exp(-delta * 3.0));
    }

    // Fuerza de resorte suave de retorno al centro (Spring Return) para que no quede varado en las esquinas
    const returnStrength = 1.3;
    orbVel.current.x -= orbPos.current.x * returnStrength * delta;
    orbVel.current.y -= orbPos.current.y * returnStrength * delta;

    // Fricción suave y amortiguada
    const friction = Math.pow(0.92, delta * 60);
    orbVel.current.x *= friction;
    orbVel.current.y *= friction;

    // Aplicar desplazamiento
    orbPos.current.x += orbVel.current.x * delta * 60;
    orbPos.current.y += orbVel.current.y * delta * 60;

    // Rebote suave en los 4 bordes del monitor
    if (orbPos.current.x <= -boundX) {
      orbPos.current.x = -boundX;
      orbVel.current.x = Math.abs(orbVel.current.x) * 0.5;
    } else if (orbPos.current.x >= boundX) {
      orbPos.current.x = boundX;
      orbVel.current.x = -Math.abs(orbVel.current.x) * 0.5;
    }

    if (orbPos.current.y <= -boundY) {
      orbPos.current.y = -boundY;
      orbVel.current.y = Math.abs(orbVel.current.y) * 0.5;
    } else if (orbPos.current.y >= boundY) {
      orbPos.current.y = boundY;
      orbVel.current.y = -Math.abs(orbVel.current.y) * 0.5;
    }

    // Flotación micro-armónica en el lugar actual
    const localHoverY = Math.sin(time * 0.8) * 0.025;

    if (groupRef.current) {
      groupRef.current.position.set(orbPos.current.x, orbPos.current.y + localHoverY, 0);
      groupRef.current.scale.setScalar(totalScale);

      // Rotación uniforme y elegante con inclinación magnética reactiva
      groupRef.current.rotation.y += delta * (0.2 + smoothRotSpeed.current * 8.0);
      groupRef.current.rotation.x = evasionTilt.current.x;
      groupRef.current.rotation.z = evasionTilt.current.y;
    }

    // Desplazamiento sutil del núcleo hacia el origen del sonido
    const dispGoal = profileKey === "escuchando" ? 0.11 : 0;
    coreDisplace.current += (dispGoal - coreDisplace.current) * (1 - Math.exp(-delta * 2.0));
    const ndx = Math.sin(tiltCurrent.current) * coreDisplace.current;
    const ndz = Math.cos(tiltCurrent.current) * coreDisplace.current;

    if (coreGroupRef.current) {
      coreGroupRef.current.position.set(ndx, 0, ndz);
    }

    // Factor de velocidad para filamentos
    const filBase = profileKey === "pensando" ? 0.3 : profileKey === "ejecutando" ? 1.4 : 1.0;
    filSpeedFactor.current += (filBase - filSpeedFactor.current) * (1 - Math.exp(-delta * 2));
  });

  const isThinking = profileKey === "pensando";
  const isExecuting = profileKey === "ejecutando";

  return (
    <group ref={groupRef}>
      {/* CAPA 1: NÚCLEO VOLUMÉTRICO */}
      <group ref={coreGroupRef}>
        <OrbCore color={activeColor.current} pulseIntensity={simAudio.current} />
      </group>

      {/* CAPA 2: ESFERA ENERGÉTICA DE PARTÍCULAS */}
      <OrbParticleCloud
        color={activeColor.current}
        vibration={smoothVibration.current}
        rotSpeed={smoothRotSpeed.current}
        cloudFocus={smoothCloudFocus.current}
        onPositionsReady={handlePositionsReady}
      />

      {/* CAPA 3: RED NEURONAL E IMPULSOS LUMINOSOS */}
      <OrbSynapses
        color={activeColor.current}
        synapseDensity={smoothSynapseDensity.current}
        isThinking={isThinking}
        cloudPositions={cloudPositions}
      />

      {/* CAPA 4: 7 ANILLOS ORBITALES Y PAQUETES DE DATOS */}
      <OrbOrbits
        color={activeColor.current}
        orbitSpeedMult={smoothOrbitSpeedMult.current}
        extMotion={smoothExtMotion.current}
      />

      {/* CAPA 5: FILAMENTOS DE ENERGÍA MAGNÉTICA */}
      <OrbFilaments
        color={activeColor.current}
        filSpeedFactor={filSpeedFactor.current}
        extMotion={smoothExtMotion.current}
      />

      {/* EXTRAS: CHISPAS REACTIVAS PARA ACCIÓN */}
      <OrbSparks color={activeColor.current} isExecuting={isExecuting} />
    </group>
  );
}

// ── ESCENA THREE.JS EN PANTALLA COMPLETA 100% TRANSPARENTE ─────────────────
interface OrbSceneProps {
  state: OrbState;
}

export function OrbScene({ state }: OrbSceneProps) {
  return (
    <Canvas
      camera={{ position: [0, 0, 7.2], fov: 40 }}
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      style={{
        position: "fixed",
        inset: 0,
        width: "100vw",
        height: "100vh",
        pointerEvents: "none",
        background: "transparent",
      }}
    >
      <ambientLight intensity={0.4} />

      {/* Orbe Cuántico Holográfico libre por toda la pantalla */}
      <OrbContent state={state} />
    </Canvas>
  );
}
