import React, { useRef, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

interface OrbFilamentsProps {
  color: THREE.Color;
  filSpeedFactor: number;
  extMotion: number;
  count?: number;
  pointsPerFilament?: number;
}

export function OrbFilaments({
  color,
  filSpeedFactor,
  extMotion,
  count = 6,
  pointsPerFilament = 24,
}: OrbFilamentsProps) {
  const groupRef = useRef<THREE.Group>(null);

  const filaments = useMemo(() => {
    return Array.from({ length: count }).map((_, i) => {
      const positions = new Float32Array(pointsPerFilament * 3);
      const geo = new THREE.BufferGeometry();
      geo.setAttribute(
        "position",
        new THREE.BufferAttribute(positions, 3).setUsage(THREE.DynamicDrawUsage)
      );

      const mat = new THREE.LineBasicMaterial({
        color: color.clone(),
        transparent: true,
        opacity: (i % 2 === 0 ? 0.38 : 0.26) * 0.8,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      });

      const line = new THREE.Line(geo, mat);

      return {
        line,
        geo,
        positions,
        index: i,
        speed: 0.35 + i * 0.12,
        phase: Math.random() * Math.PI * 2,
      };
    });
  }, [count, pointsPerFilament]);

  useFrame((state) => {
    const time = state.clock.getElapsedTime();

    filaments.forEach((fil) => {
      const mat = fil.line.material as THREE.LineBasicMaterial;
      mat.color.copy(color);
      mat.opacity =
        (fil.index % 2 === 0 ? 0.38 : 0.26) * (0.7 + 0.3 * extMotion);

      const pos = fil.positions;
      const filSpeed = time * fil.speed * filSpeedFactor + fil.phase;

      for (let k = 0; k < pointsPerFilament; k++) {
        const u = k / (pointsPerFilament - 1);
        const angle = u * Math.PI * 2 + filSpeed;
        const rad = 1.05 + 0.45 * Math.sin(u * Math.PI * 3 + filSpeed * 0.8);
        const height = 0.6 * Math.sin(u * Math.PI * 2 + filSpeed * 0.5);

        pos[k * 3] = Math.cos(angle) * rad;
        pos[k * 3 + 1] = height;
        pos[k * 3 + 2] = Math.sin(angle) * rad;
      }

      fil.geo.attributes.position.needsUpdate = true;
    });
  });

  return (
    <group ref={groupRef}>
      {filaments.map((fil, idx) => (
        <primitive key={idx} object={fil.line} />
      ))}
    </group>
  );
}
