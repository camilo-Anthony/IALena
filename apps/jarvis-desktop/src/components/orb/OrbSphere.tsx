import React, { useRef, useMemo } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";

interface OrbSphereProps {
  stateName: string;
}

// ── CUSTOM SHADER PARA EL ORBE VIVO ──────────────────────────────────────────
const OrbVertexShader = `
  uniform float uTime;
  uniform float uBreath;
  uniform float uExcitement;
  uniform vec3 uFocusPoint; // Posición de mirada (cursor en 3D)
  uniform float uTremor;    // Microtemblor de transición

  varying vec3 vNormal;
  varying vec3 vPosition;
  varying vec3 vViewPosition;

  // Ruido pseudo-aleatorio para deformación biológica
  float hash(vec3 p) {
    p = fract(p * 0.3183099 + vec3(0.1, 0.1, 0.1));
    p *= 17.0;
    return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
  }

  float noise(in vec3 x) {
    vec3 i = floor(x);
    vec3 f = fract(x);
    f = f*f*(3.0-2.0*f);
    return mix(mix(mix(hash(i+vec3(0,0,0)), hash(i+vec3(1,0,0)),f.x),
                   mix(hash(i+vec3(0,1,0)), hash(i+vec3(1,1,0)),f.x),f.y),
               mix(mix(hash(i+vec3(0,0,1)), hash(i+vec3(1,0,1)),f.x),
                   mix(hash(i+vec3(0,1,1)), hash(i+vec3(1,1,1)),f.x),f.y),f.z);
  }

  void main() {
    vNormal = normalize(normalMatrix * normal);
    vPosition = position;

    // 1. Respiración (Deformación asimétrica biológica)
    float breathDeform = uBreath * 0.08;

    // 2. Micro-temblor (Vibración caótica de alta frecuencia en transiciones)
    vec3 tremorOffset = vec3(0.0);
    if (uTremor > 0.01) {
      float tFreq = uTime * 120.0;
      tremorOffset = vec3(
        sin(tFreq + position.x) * 0.003 * uTremor,
        cos(tFreq * 1.3 + position.y) * 0.003 * uTremor,
        sin(tFreq * 0.8 + position.z) * 0.003 * uTremor
      );
    }

    // 3. Mirada (Atracción/Deformación hacia focus point)
    vec3 worldPos = (modelMatrix * vec4(position, 1.0)).xyz;
    vec3 toFocus = uFocusPoint - worldPos;
    float distToFocus = length(toFocus);
    vec3 lookDeform = vec3(0.0);
    if (distToFocus > 0.1) {
      // Deformar sutilmente los vértices en la dirección del cursor con caída suave
      float strength = smoothstep(6.0, 0.0, distToFocus) * 0.06;
      lookDeform = normalize(toFocus) * strength;
    }

    // 4. Ondas biológicas de ruido (sway suave constante)
    float wave = noise(position * 2.0 + uTime * (1.0 + uExcitement * 2.0)) * 0.05;

    // Combinar todas las deformaciones biológicas
    vec3 newPosition = position + (normal * (breathDeform + wave)) + lookDeform + tremorOffset;

    vec4 mvPosition = modelViewMatrix * vec4(newPosition, 1.0);
    vViewPosition = -mvPosition.xyz;
    gl_Position = projectionMatrix * mvPosition;
  }
`;

const OrbFragmentShader = `
  uniform vec3 uColor;
  uniform float uTime;
  uniform float uExcitement;
  uniform float uBlink; // Parpadeo aleatorio (reducción de brillo temporal)

  varying vec3 vNormal;
  varying vec3 vPosition;
  varying vec3 vViewPosition;

  void main() {
    // Vector de vista normalizado
    vec3 normal = normalize(vNormal);
    vec3 viewDir = normalize(vViewPosition);

    // Brillo Fresnel holográfico (más brillante en los bordes)
    float fresnel = pow(1.0 - max(dot(normal, viewDir), 0.0), 3.0);

    // Ondulación de brillo de plasma interno
    float plasma = sin(vPosition.x * 3.0 + uTime) * cos(vPosition.y * 3.0 + uTime) * 0.15;

    // Brillo base + efecto plasma + factor de excitación
    float intensity = (0.4 + fresnel * 0.8 + plasma) * uBlink;
    
    // Intensificar color basado en excitación
    vec3 finalColor = mix(uColor, vec3(1.0), fresnel * 0.3 * (1.0 + uExcitement));

    gl_FragColor = vec4(finalColor * intensity, intensity * 0.85);
  }
`;

export function OrbSphere({ stateName }: OrbSphereProps) {
  const meshRef = useRef<THREE.Mesh>(null);
  const materialRef = useRef<THREE.ShaderMaterial>(null);
  const { mouse, viewport } = useThree();

  // Estados internos interpolados para comportamiento
  const behavior = useRef({
    breath: 1.0,
    breathTime: 0.0,
    excitement: 0.0,
    tremor: 0.0,
    blink: 1.0,
    color: new THREE.Color("#0066ff"),
    focus: new THREE.Vector3(0, 0, 0),
    sleepFactor: 1.0,
  });

  // Configuración de metas según el estado lógico de JARVIS
  const targets = useMemo(() => {
    switch (stateName) {
      case "listening":
        return { color: "#00ff88", excitement: 0.5, speed: 1.6, baseBpm: 75 };
      case "speaking":
        return { color: "#00f5ff", excitement: 0.7, speed: 2.2, baseBpm: 95 };
      case "thinking_fast":
        return { color: "#ffd700", excitement: 0.9, speed: 3.5, baseBpm: 110 };
      case "working_slow":
        return { color: "#ff6b35", excitement: 0.8, speed: 2.8, baseBpm: 90 };
      case "reconnecting":
      case "confirmation_pending":
        return { color: "#7c3aed", excitement: 0.3, speed: 1.2, baseBpm: 65 };
      case "error":
        return { color: "#ff3366", excitement: 1.0, speed: 5.0, baseBpm: 120 };
      case "dormant":
      default:
        return { color: "#0055dd", excitement: 0.0, speed: 0.4, baseBpm: 14 }; // 14 ciclos de respiración
    }
  }, [stateName]);

  // Timers e impulsos aleatorios
  const lastState = useRef(stateName);
  const blinkTimer = useRef(0);
  const sleepTimer = useRef(0);

  // Inicializar Shaders con uniforms
  const uniforms = useMemo(() => {
    return {
      uTime: { value: 0 },
      uBreath: { value: 0 },
      uExcitement: { value: 0 },
      uTremor: { value: 0 },
      uBlink: { value: 1.0 },
      uColor: { value: new THREE.Color("#0066ff") },
      uFocusPoint: { value: new THREE.Vector3(0, 0, 0) },
    };
  }, []);

  useFrame((state, delta) => {
    const t = state.clock.getElapsedTime();
    const b = behavior.current;

    // 1. Detección de cambio de estado para micro-temblor
    if (stateName !== lastState.current) {
      b.tremor = 1.0;
      lastState.current = stateName;
    }
    b.tremor = THREE.MathUtils.lerp(b.tremor, 0.0, 0.08); // Decay del temblor

    // 2. Respiración asimétrica biológica
    // Inhalación rápida (0.4s), Exhalación suave (0.8s)
    const bpm = targets.baseBpm;
    const cycleDuration = 60 / bpm;
    b.breathTime += delta;
    if (b.breathTime >= cycleDuration) {
      b.breathTime = 0;
    }
    const ratio = b.breathTime / cycleDuration;
    // Función asimétrica: subida exponencial rápida, bajada suave senoidal
    if (ratio < 0.35) {
      // Inhalación
      b.breath = Math.pow(ratio / 0.35, 2.0);
    } else {
      // Exhalación
      b.breath = Math.cos(((ratio - 0.35) / 0.65) * Math.PI * 0.5);
    }

    // 3. Parpadeo aleatorio (Blink)
    blinkTimer.current -= delta;
    if (blinkTimer.current <= 0) {
      b.blink = 0.3; // Caída de brillo
      blinkTimer.current = 4.0 + Math.random() * 4.0; // Próximo parpadeo en 4-8s
    } else {
      b.blink = THREE.MathUtils.lerp(b.blink, 1.0, 0.15); // Recuperación
    }

    // 4. Timidez física (Seguimiento e interactividad con el cursor)
    // El cursor del ratón en espacio normalizado 2D se proyecta
    const targetFocus = new THREE.Vector3(
      (mouse.x * viewport.width) / 2,
      (mouse.y * viewport.height) / 2,
      0
    );
    b.focus.lerp(targetFocus, 0.08);

    // Repulsión física sutil si el cursor se acerca mucho al centro del orbe
    const distToCenter = targetFocus.length();
    let repulsion = 1.0;
    if (distToCenter < 2.0) {
      repulsion = 0.95 - (0.05 * (1.0 - distToCenter / 2.0)); // Encoge 3-5%
    } else {
      repulsion = 1.02; // Estira ligeramente al alejarse
    }

    // 5. Interpolación suave de variables visuales
    b.excitement = THREE.MathUtils.lerp(b.excitement, targets.excitement, 0.05);
    const targetCol = new THREE.Color(targets.color);
    b.color.lerp(targetCol, 0.04);

    // Aplicar transformaciones básicas de matriz
    if (meshRef.current) {
      meshRef.current.rotation.y = t * 0.08;
      // Inclinación cerebellar de cabeza al "pensar"
      const headTilt = stateName === "thinking_fast" ? 0.18 : 0.0;
      meshRef.current.rotation.x = THREE.MathUtils.lerp(meshRef.current.rotation.x, headTilt, 0.05);

      const finalScale = 1.0 * repulsion;
      meshRef.current.scale.lerp(new THREE.Vector3(finalScale, finalScale, finalScale), 0.1);
    }

    // 6. Actualizar uniforms del shader
    if (materialRef.current) {
      materialRef.current.uniforms.uTime.value = t;
      materialRef.current.uniforms.uBreath.value = b.breath;
      materialRef.current.uniforms.uExcitement.value = b.excitement;
      materialRef.current.uniforms.uTremor.value = b.tremor;
      materialRef.current.uniforms.uBlink.value = b.blink;
      materialRef.current.uniforms.uColor.value.copy(b.color);
      materialRef.current.uniforms.uFocusPoint.value.copy(b.focus);
    }
  });

  return (
    <mesh ref={meshRef}>
      <sphereGeometry args={[1.1, 128, 128]} />
      <shaderMaterial
        ref={materialRef}
        vertexShader={OrbVertexShader}
        fragmentShader={OrbFragmentShader}
        uniforms={uniforms}
        transparent
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </mesh>
  );
}
