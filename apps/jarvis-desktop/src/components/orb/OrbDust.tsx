import React, { useRef, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

interface OrbDustProps {
  color: THREE.Color;
  count?: number;
}

const DustVertexShader = `
  uniform float uTime;
  varying float vAlpha;
  void main() {
    vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
    gl_Position = projectionMatrix * mvPosition;

    float dist = length(position);
    vAlpha = smoothstep(5.0, 2.5, dist) * smoothstep(1.8, 2.4, dist);
    gl_PointSize = 0.038 * (320.0 / -mvPosition.z);
  }
`;

const DustFragmentShader = `
  uniform vec3 uColor;
  varying float vAlpha;
  void main() {
    float d = length(gl_PointCoord - vec2(0.5)) * 2.0;
    if (d > 1.0) discard;
    float a = pow(1.0 - d, 2.0);
    gl_FragColor = vec4(uColor * 1.1, a * vAlpha * 0.5);
  }
`;

export function OrbDust({ color, count = 450 }: OrbDustProps) {
  const pointsRef = useRef<THREE.Points>(null);
  const shaderMatRef = useRef<THREE.ShaderMaterial>(null);

  const { geo, dustPos, dustBasePos, dustPhases } = useMemo(() => {
    const pos = new Float32Array(count * 3);
    const basePos = new Float32Array(count * 3);
    const phases = new Float32Array(count);

    for (let i = 0; i < count; i++) {
      const rad = 2.4 + Math.random() * 2.8;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);

      const x = rad * Math.sin(phi) * Math.cos(theta);
      const y = rad * Math.cos(phi) * 0.7;
      const z = rad * Math.sin(phi) * Math.sin(theta);

      basePos[i * 3] = x;
      basePos[i * 3 + 1] = y;
      basePos[i * 3 + 2] = z;

      pos[i * 3] = x;
      pos[i * 3 + 1] = y;
      pos[i * 3 + 2] = z;

      phases[i] = Math.random() * Math.PI * 2;
    }

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute(
      "position",
      new THREE.BufferAttribute(pos, 3).setUsage(THREE.DynamicDrawUsage)
    );

    return {
      geo: geometry,
      dustPos: pos,
      dustBasePos: basePos,
      dustPhases: phases,
    };
  }, [count]);

  const uniforms = useMemo(
    () => ({
      uTime: { value: 0 },
      uColor: { value: color.clone() },
    }),
    []
  );

  useFrame((state) => {
    const time = state.clock.getElapsedTime();

    if (shaderMatRef.current) {
      shaderMatRef.current.uniforms.uTime.value = time;
      shaderMatRef.current.uniforms.uColor.value.copy(color);
    }

    const posAttr = geo.attributes.position as THREE.BufferAttribute;
    for (let i = 0; i < count; i++) {
      const b = i * 3;
      const ph = dustPhases[i];
      const dr = 1.0 + 0.08 * Math.sin(time * 0.3 + ph);

      dustPos[b] = dustBasePos[b] * dr + Math.sin(time * 0.2 + ph) * 0.08;
      dustPos[b + 1] =
        dustBasePos[b + 1] * dr + Math.cos(time * 0.25 + ph) * 0.08;
      dustPos[b + 2] = dustBasePos[b + 2] * dr;
    }
    posAttr.needsUpdate = true;
  });

  return (
    <points ref={pointsRef} geometry={geo}>
      <shaderMaterial
        ref={shaderMatRef}
        vertexShader={DustVertexShader}
        fragmentShader={DustFragmentShader}
        uniforms={uniforms}
        transparent
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
}
