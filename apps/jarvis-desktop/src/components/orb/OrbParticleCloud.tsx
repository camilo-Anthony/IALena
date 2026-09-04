import React, { useRef, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

interface OrbParticleCloudProps {
  color: THREE.Color;
  vibration: number;
  rotSpeed: number;
  cloudFocus: number;
  particleCount?: number;
  onPositionsReady?: (positions: Float32Array) => void;
}

const ParticleCloudVertexShader = `
  attribute float aSize;
  attribute float aSeed;
  uniform float uTime;
  uniform float uVibration;
  uniform vec3 uColor;

  varying float vAlpha;
  varying float vSize;

  void main() {
    vec3 pos = position;

    // Deriva lenta de partículas flotantes
    float floatAngle = uTime * (0.2 + 0.3 * sin(aSeed)) + aSeed;
    pos.x += sin(floatAngle) * 0.025;
    pos.y += cos(floatAngle * 0.8) * 0.025;
    pos.z += sin(floatAngle * 1.2) * 0.025;

    // Vibración en cambios de estado o audio
    if (uVibration > 0.01) {
      pos += vec3(
        sin(uTime * 30.0 + aSeed) * 0.02 * uVibration,
        cos(uTime * 25.0 + aSeed * 1.5) * 0.02 * uVibration,
        sin(uTime * 28.0 + aSeed * 2.0) * 0.02 * uVibration
      );
    }

    vec4 mvPosition = modelViewMatrix * vec4(pos, 1.0);
    gl_Position = projectionMatrix * mvPosition;

    // Centelleo armónico (twinkle)
    float twinkle = 0.4 + 0.6 * sin(uTime * (1.5 + sin(aSeed)) + aSeed * 6.28);
    vAlpha = twinkle;

    gl_PointSize = aSize * (1.0 + twinkle * 0.4) * (380.0 / -mvPosition.z);
  }
`;

const ParticleCloudFragmentShader = `
  uniform vec3 uColor;
  varying float vAlpha;

  void main() {
    // Sprite circular radial suave
    vec2 coord = gl_PointCoord - vec2(0.5);
    float dist = length(coord) * 2.0;
    if (dist > 1.0) discard;

    float coreGlow = smoothstep(1.0, 0.0, dist);
    coreGlow = pow(coreGlow, 1.8);

    vec3 col = mix(vec3(1.0), uColor, dist * 0.7);
    gl_FragColor = vec4(col * 1.25, coreGlow * vAlpha * 0.7);
  }
`;

export function OrbParticleCloud({
  color,
  vibration,
  rotSpeed,
  cloudFocus,
  particleCount = 6000,
  onPositionsReady,
}: OrbParticleCloudProps) {
  const pointsRef = useRef<THREE.Points>(null);
  const shaderMatRef = useRef<THREE.ShaderMaterial>(null);

  const { geometry, positions } = useMemo(() => {
    const pos = new Float32Array(particleCount * 3);
    const sizes = new Float32Array(particleCount);
    const seeds = new Float32Array(particleCount);

    const goldenRatio = (1 + Math.sqrt(5)) / 2;
    for (let i = 0; i < particleCount; i++) {
      const theta = (2 * Math.PI * i) / goldenRatio;
      const phi = Math.acos(1 - (2 * (i + 0.5)) / particleCount);
      const rad = 0.88 + Math.pow(Math.random(), 1.5) * 0.44;

      const dx = Math.sin(phi) * Math.cos(theta);
      const dy = Math.cos(phi);
      const dz = Math.sin(phi) * Math.sin(theta);

      pos[i * 3] = dx * rad;
      pos[i * 3 + 1] = dy * rad;
      pos[i * 3 + 2] = dz * rad;

      sizes[i] = 0.012 + Math.pow(Math.random(), 3.0) * 0.095;
      seeds[i] = Math.random() * 100.0;
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    geo.setAttribute("aSize", new THREE.BufferAttribute(sizes, 1));
    geo.setAttribute("aSeed", new THREE.BufferAttribute(seeds, 1));

    return { geometry: geo, positions: pos };
  }, [particleCount]);

  React.useEffect(() => {
    if (onPositionsReady && positions) {
      onPositionsReady(positions);
    }
  }, [positions, onPositionsReady]);

  const uniforms = useMemo(
    () => ({
      uTime: { value: 0 },
      uColor: { value: color.clone() },
      uVibration: { value: 0.0 },
    }),
    []
  );

  useFrame((state, delta) => {
    const t = state.clock.getElapsedTime();
    if (shaderMatRef.current) {
      shaderMatRef.current.uniforms.uTime.value = t;
      shaderMatRef.current.uniforms.uColor.value.copy(color);
      shaderMatRef.current.uniforms.uVibration.value = vibration;
    }
    if (pointsRef.current) {
      pointsRef.current.rotation.y += delta * 0.25;
      pointsRef.current.scale.setScalar(cloudFocus);
    }
  });

  return (
    <points ref={pointsRef} geometry={geometry}>
      <shaderMaterial
        ref={shaderMatRef}
        vertexShader={ParticleCloudVertexShader}
        fragmentShader={ParticleCloudFragmentShader}
        uniforms={uniforms}
        transparent
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
}
export { ParticleCloudVertexShader, ParticleCloudFragmentShader };
