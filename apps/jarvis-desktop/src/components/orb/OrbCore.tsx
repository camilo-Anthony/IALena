import React, { useRef, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { createGlowTexture } from "./OrbTextures";

interface OrbCoreProps {
  color: THREE.Color;
  pulseIntensity: number;
}

const CoreVertexShader = `
  varying vec3 vNormal;
  varying vec3 vViewPosition;
  varying vec3 vWorldPosition;
  uniform float uTime;
  uniform float uPulse;

  void main() {
    vNormal = normalize(normalMatrix * normal);
    vec4 worldPosition = modelMatrix * vec4(position, 1.0);
    vWorldPosition = worldPosition.xyz;
    vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
    vViewPosition = -mvPosition.xyz;

    // Turbulencia orgánica de superficie
    float p = sin(position.x * 6.0 + uTime * 3.0) * cos(position.y * 6.0 + uTime * 2.5) * sin(position.z * 6.0 + uTime * 3.5);
    vec3 displacedPos = position + normal * (p * 0.02 + uPulse * 0.06);

    gl_Position = projectionMatrix * modelViewMatrix * vec4(displacedPos, 1.0);
  }
`;

const CoreFragmentShader = `
  uniform vec3 uColorCore;
  uniform vec3 uColorCyan;
  uniform vec3 uColorMain;
  uniform float uPulse;
  uniform float uIntensity;
  uniform float uTime;

  varying vec3 vNormal;
  varying vec3 vViewPosition;
  varying vec3 vWorldPosition;

  void main() {
    vec3 normal = normalize(vNormal);
    vec3 viewDir = normalize(vViewPosition);

    float fresnel = pow(1.0 - max(dot(normal, viewDir), 0.0), 2.5);
    float centerGlow = pow(max(dot(normal, viewDir), 0.0), 4.0);

    // Simulación de ruido de plasma
    float noise = sin(vWorldPosition.x * 12.0 + uTime * 4.0) * sin(vWorldPosition.y * 12.0 + uTime * 3.0) * sin(vWorldPosition.z * 12.0 + uTime * 5.0);
    noise = noise * 0.5 + 0.5;

    vec3 col = uColorMain;
    col = mix(col, uColorCore, centerGlow * 0.6);

    float alpha = (0.9 + centerGlow * 0.6) * uIntensity;
    col *= (1.3 + centerGlow * 0.8);

    gl_FragColor = vec4(col, min(alpha, 1.0));
  }
`;

export function OrbCore({ color, pulseIntensity }: OrbCoreProps) {
  const meshRef = useRef<THREE.Mesh>(null);
  const shaderMatRef = useRef<THREE.ShaderMaterial>(null);
  const spriteRef = useRef<THREE.Sprite>(null);

  const glowMap = useMemo(
    () => createGlowTexture(512, "rgba(255,255,255,1.0)", "rgba(255,255,255,0.0)"),
    []
  );

  const uniforms = useMemo(
    () => ({
      uTime: { value: 0 },
      uColorCore: { value: new THREE.Color("#FFFFFF") },
      uColorCyan: { value: new THREE.Color("#00FFFF") },
      uColorMain: { value: color.clone() },
      uPulse: { value: 0.0 },
      uIntensity: { value: 1.0 },
    }),
    []
  );

  useFrame((state) => {
    const t = state.clock.getElapsedTime();
    if (shaderMatRef.current) {
      shaderMatRef.current.uniforms.uTime.value = t;
      shaderMatRef.current.uniforms.uPulse.value = pulseIntensity;
      shaderMatRef.current.uniforms.uColorMain.value.copy(color);
    }
    if (spriteRef.current) {
      const s = 1.35 + pulseIntensity * 0.35;
      spriteRef.current.scale.set(s, s, s);
      const mat = spriteRef.current.material as THREE.SpriteMaterial;
      mat.color.copy(color);
    }
  });

  return (
    <group>
      {/* Malla volumétrica de plasma (Icosaedro) */}
      <mesh ref={meshRef}>
        <icosahedronGeometry args={[0.52, 3]} />
        <shaderMaterial
          ref={shaderMatRef}
          vertexShader={CoreVertexShader}
          fragmentShader={CoreFragmentShader}
          uniforms={uniforms}
          transparent
          depthWrite={false}
          blending={THREE.AdditiveBlending}
        />
      </mesh>

      {/* Destello incandescente central */}
      <sprite ref={spriteRef} visible={true}>
        <spriteMaterial
          map={glowMap}
          transparent
          depthWrite={false}
          blending={THREE.AdditiveBlending}
          opacity={0.65}
        />
      </sprite>
    </group>
  );
}
