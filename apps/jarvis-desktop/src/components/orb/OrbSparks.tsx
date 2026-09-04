import React, { useRef, useMemo, useImperativeHandle, forwardRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

export interface OrbSparksRef {
  spawnSparks: (count?: number) => void;
}

interface OrbSparksProps {
  color: THREE.Color;
  isExecuting: boolean;
}

const SparkVertexShader = `
  attribute float aAlpha;
  varying float vAlpha;
  void main() {
    vAlpha = aAlpha;
    vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
    gl_PointSize = 0.06 * aAlpha * (300.0 / -mvPosition.z);
    gl_Position = projectionMatrix * mvPosition;
  }
`;

const SparkFragmentShader = `
  uniform vec3 uColor;
  varying float vAlpha;
  void main() {
    float d = length(gl_PointCoord - vec2(0.5)) * 2.0;
    if (d > 1.0) discard;
    gl_FragColor = vec4(uColor * 1.5, (1.0 - d) * vAlpha);
  }
`;

export const OrbSparks = forwardRef<OrbSparksRef, OrbSparksProps>(
  ({ color, isExecuting }, ref) => {
    const SPARK_COUNT = 80;
    const pointsRef = useRef<THREE.Points>(null);
    const shaderMatRef = useRef<THREE.ShaderMaterial>(null);

    const { geo, sparkPos, sparkVel, sparkLife, sparkAlphas } = useMemo(() => {
      const pos = new Float32Array(SPARK_COUNT * 3);
      const vel = new Float32Array(SPARK_COUNT * 3);
      const life = new Float32Array(SPARK_COUNT);
      const alphas = new Float32Array(SPARK_COUNT);

      for (let i = 0; i < SPARK_COUNT; i++) {
        life[i] = -1.0;
      }

      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute(
        "position",
        new THREE.BufferAttribute(pos, 3).setUsage(THREE.DynamicDrawUsage)
      );
      geometry.setAttribute(
        "aAlpha",
        new THREE.BufferAttribute(alphas, 1).setUsage(THREE.DynamicDrawUsage)
      );

      return {
        geo: geometry,
        sparkPos: pos,
        sparkVel: vel,
        sparkLife: life,
        sparkAlphas: alphas,
      };
    }, []);

    const spawnSpark = () => {
      for (let i = 0; i < SPARK_COUNT; i++) {
        if (sparkLife[i] <= 0) {
          const theta = Math.random() * Math.PI * 2;
          const phi = Math.acos(2 * Math.random() - 1);
          const speed = 1.2 + Math.random() * 2.2;

          sparkPos[i * 3] = Math.sin(phi) * Math.cos(theta) * 0.5;
          sparkPos[i * 3 + 1] = Math.cos(phi) * 0.5;
          sparkPos[i * 3 + 2] = Math.sin(phi) * Math.sin(theta) * 0.5;

          sparkVel[i * 3] = Math.sin(phi) * Math.cos(theta) * speed;
          sparkVel[i * 3 + 1] = Math.cos(phi) * speed;
          sparkVel[i * 3 + 2] = Math.sin(phi) * Math.sin(theta) * speed;

          sparkLife[i] = 0.5 + Math.random() * 0.5;
          break;
        }
      }
    };

    useImperativeHandle(ref, () => ({
      spawnSparks: (n = 10) => {
        for (let k = 0; k < n; k++) spawnSpark();
      },
    }));

    const uniforms = useMemo(
      () => ({
        uColor: { value: color.clone() },
      }),
      []
    );

    useFrame((_, delta) => {
      if (shaderMatRef.current) {
        shaderMatRef.current.uniforms.uColor.value.copy(color);
      }

      if (isExecuting && Math.random() < 0.25) {
        spawnSpark();
      }

      for (let i = 0; i < SPARK_COUNT; i++) {
        if (sparkLife[i] > 0) {
          sparkLife[i] -= delta;
          const dist = Math.max(
            0.15,
            Math.sqrt(
              sparkPos[i * 3] ** 2 +
                sparkPos[i * 3 + 1] ** 2 +
                sparkPos[i * 3 + 2] ** 2
            )
          );
          const pull = (isExecuting ? 1.6 : 0.6) / dist;
          sparkVel[i * 3] -= sparkPos[i * 3] * pull * delta;
          sparkVel[i * 3 + 1] -= sparkPos[i * 3 + 1] * pull * delta;
          sparkVel[i * 3 + 2] -= sparkPos[i * 3 + 2] * pull * delta;

          sparkPos[i * 3] += sparkVel[i * 3] * delta;
          sparkPos[i * 3 + 1] += sparkVel[i * 3 + 1] * delta;
          sparkPos[i * 3 + 2] += sparkVel[i * 3 + 2] * delta;

          sparkAlphas[i] = Math.max(0.0, sparkLife[i] / 0.5);
        } else {
          sparkAlphas[i] = 0.0;
        }
      }

      geo.attributes.position.needsUpdate = true;
      geo.attributes.aAlpha.needsUpdate = true;
    });

    return (
      <points ref={pointsRef} geometry={geo}>
        <shaderMaterial
          ref={shaderMatRef}
          vertexShader={SparkVertexShader}
          fragmentShader={SparkFragmentShader}
          uniforms={uniforms}
          transparent
          depthWrite={false}
          blending={THREE.AdditiveBlending}
        />
      </points>
    );
  }
);
