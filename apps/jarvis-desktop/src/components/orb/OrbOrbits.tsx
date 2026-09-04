import React, { useRef, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { createGlowTexture } from "./OrbTextures";

interface OrbOrbitsProps {
  color: THREE.Color;
  orbitSpeedMult: number;
  extMotion: number;
}

interface OrbitConfig {
  radius: number;
  tube: number;
  rotX: number;
  rotY: number;
  speed: number;
  calm: number;
  opacity: number;
}

const ORBIT_CONFIGS: OrbitConfig[] = [
  { radius: 1.08, tube: 0.006, rotX: 0.25, rotY: 0.1,  speed: 0.012, calm: 0.30, opacity: 0.65 },
  { radius: 1.25, tube: 0.005, rotX: 1.15, rotY: -0.4, speed: -0.016, calm: 0.08, opacity: 0.55 },
  { radius: 1.44, tube: 0.007, rotX: -0.5, rotY: 0.8,  speed: 0.009, calm: 0.55, opacity: 0.70 },
  { radius: 1.62, tube: 0.004, rotX: 0.9,  rotY: 0.3,  speed: -0.022, calm: 0.12, opacity: 0.50 },
  { radius: 1.82, tube: 0.005, rotX: -1.2, rotY: -0.7, speed: 0.014, calm: 0.40, opacity: 0.60 },
  { radius: 2.02, tube: 0.006, rotX: 0.45, rotY: 1.1,  speed: -0.010, calm: 0.05, opacity: 0.45 },
  { radius: 2.22, tube: 0.005, rotX: -0.8, rotY: 0.2,  speed: 0.018, calm: 0.70, opacity: 0.40 },
];

const TrailVertexShader = `
  attribute float aAlpha;
  varying float vAlpha;
  void main() {
    vAlpha = aAlpha;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const TrailFragmentShader = `
  uniform vec3 uColor;
  varying float vAlpha;
  void main() { gl_FragColor = vec4(uColor * 1.4, vAlpha); }
`;

export function OrbOrbits({ color, orbitSpeedMult, extMotion }: OrbOrbitsProps) {
  const groupRef = useRef<THREE.Group>(null);
  const glowMap = useMemo(() => createGlowTexture(256, "rgba(255,255,255,1.0)", "rgba(255,255,255,0.0)"), []);

  const orbits = useMemo(() => {
    return ORBIT_CONFIGS.map((cfg) => {
      const trailLength = 16;
      const trailPositions = new Float32Array(trailLength * 3);
      const trailAlphas = new Float32Array(trailLength);
      for (let t = 0; t < trailLength; t++) {
        trailAlphas[t] = Math.pow((trailLength - t) / trailLength, 2.0) * 0.8;
      }
      const trailGeo = new THREE.BufferGeometry();
      trailGeo.setAttribute("position", new THREE.BufferAttribute(trailPositions, 3));
      trailGeo.setAttribute("aAlpha", new THREE.BufferAttribute(trailAlphas, 1));

      return {
        cfg,
        angle: Math.random() * Math.PI * 2,
        packetSpeed: 1.2 + Math.random() * 1.8,
        trailPositions,
        trailGeo,
        ringGroupRef: React.createRef<THREE.Group>(),
        ringMeshRef: React.createRef<THREE.Mesh>(),
        ghostMeshRef: React.createRef<THREE.Mesh>(),
        packetSpriteRef: React.createRef<THREE.Sprite>(),
        trailLineRef: React.createRef<THREE.Line>(),
      };
    });
  }, []);

  useFrame((state, delta) => {
    orbits.forEach((orb) => {
      if (!orb.ringGroupRef.current) return;

      const calmK = orb.cfg.calm;
      orb.ringGroupRef.current.rotation.z +=
        delta * orb.cfg.speed * orbitSpeedMult * extMotion * calmK;

      orb.angle += delta * orb.packetSpeed * orbitSpeedMult * calmK;
      const px = Math.cos(orb.angle) * orb.cfg.radius;
      const py = Math.sin(orb.angle) * orb.cfg.radius;

      if (orb.packetSpriteRef.current) {
        orb.packetSpriteRef.current.position.set(px, py, 0);
        const mat = orb.packetSpriteRef.current.material as THREE.SpriteMaterial;
        mat.color.copy(color);
      }

      if (orb.ringMeshRef.current) {
        const mat = orb.ringMeshRef.current.material as THREE.MeshBasicMaterial;
        mat.color.copy(color);
      }
      if (orb.ghostMeshRef.current) {
        const mat = orb.ghostMeshRef.current.material as THREE.MeshBasicMaterial;
        mat.color.copy(color);
      }

      if (orb.trailLineRef.current) {
        const mat = orb.trailLineRef.current.material as THREE.ShaderMaterial;
        if (mat.uniforms && mat.uniforms.uColor) {
          mat.uniforms.uColor.value.copy(color);
        }

        const trailAttr = orb.trailGeo.attributes.position as THREE.BufferAttribute;
        for (let t = orb.trailPositions.length / 3 - 1; t > 0; t--) {
          orb.trailPositions[t * 3] = orb.trailPositions[(t - 1) * 3];
          orb.trailPositions[t * 3 + 1] = orb.trailPositions[(t - 1) * 3 + 1];
          orb.trailPositions[t * 3 + 2] = orb.trailPositions[(t - 1) * 3 + 2];
        }
        orb.trailPositions[0] = px;
        orb.trailPositions[1] = py;
        orb.trailPositions[2] = 0;
        trailAttr.needsUpdate = true;
      }
    });
  });

  return (
    <group ref={groupRef}>
      {orbits.map((orb, idx) => (
        <group
          key={idx}
          ref={orb.ringGroupRef}
          rotation={[orb.cfg.rotX, orb.cfg.rotY, 0]}
        >
          {/* Anillo Principal */}
          <mesh ref={orb.ringMeshRef}>
            <torusGeometry args={[orb.cfg.radius, orb.cfg.tube, 8, 160]} />
            <meshBasicMaterial
              color={color}
              transparent
              opacity={orb.cfg.opacity}
              blending={THREE.AdditiveBlending}
              depthWrite={false}
            />
          </mesh>

          {/* Anillo Fantasma Echo */}
          <mesh ref={orb.ghostMeshRef} scale={1.02}>
            <torusGeometry args={[orb.cfg.radius, orb.cfg.tube * 0.5, 6, 120]} />
            <meshBasicMaterial
              color={color}
              transparent
              opacity={orb.cfg.opacity * 0.3}
              blending={THREE.AdditiveBlending}
              depthWrite={false}
            />
          </mesh>

          {/* Paquete de Datos Luminoso */}
          <sprite ref={orb.packetSpriteRef} scale={[0.18, 0.18, 0.18]}>
            <spriteMaterial
              map={glowMap}
              color={color}
              blending={THREE.AdditiveBlending}
              transparent
              depthWrite={false}
            />
          </sprite>

          {/* Estela del Paquete */}
          <primitive
            object={
              new THREE.Line(
                orb.trailGeo,
                new THREE.ShaderMaterial({
                  uniforms: { uColor: { value: color.clone() } },
                  transparent: true,
                  depthWrite: false,
                  blending: THREE.AdditiveBlending,
                  vertexShader: TrailVertexShader,
                  fragmentShader: TrailFragmentShader,
                })
              )
            }
            ref={orb.trailLineRef}
          />
        </group>
      ))}
    </group>
  );
}
