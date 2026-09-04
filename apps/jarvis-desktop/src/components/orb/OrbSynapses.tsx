import React, { useRef, useMemo, useEffect } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

interface OrbSynapsesProps {
  color: THREE.Color;
  synapseDensity: number;
  isThinking: boolean;
  cloudPositions?: Float32Array | null;
  count?: number;
}

const SynapseVertexShader = `
  attribute float aAlpha;
  varying float vAlpha;
  void main() {
    vAlpha = aAlpha;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const SynapseFragmentShader = `
  uniform vec3 uColor;
  varying float vAlpha;
  void main() {
    gl_FragColor = vec4(uColor * 1.2, vAlpha * 0.4);
  }
`;

const PulseVertexShader = `
  attribute float aAlpha;
  uniform float uBoost;
  varying float vA;
  void main() {
    vA = aAlpha * uBoost;
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    gl_PointSize = 0.055 * vA * (300.0 / max(0.1, -mv.z));
    gl_Position = projectionMatrix * mv;
  }
`;

const PulseFragmentShader = `
  uniform vec3 uColor;
  varying float vA;
  void main() {
    float d = length(gl_PointCoord - vec2(0.5)) * 2.0;
    if (d > 1.0) discard;
    gl_FragColor = vec4(uColor * 2.2, (1.0 - d) * vA);
  }
`;

export function OrbSynapses({
  color,
  synapseDensity,
  isThinking,
  cloudPositions,
  count = 320,
}: OrbSynapsesProps) {
  const lineSegmentsRef = useRef<THREE.LineSegments>(null);
  const lineShaderMatRef = useRef<THREE.ShaderMaterial>(null);
  const pulsePointsRef = useRef<THREE.Points>(null);
  const pulseShaderMatRef = useRef<THREE.ShaderMaterial>(null);

  const { lineGeo, pulseGeo, synapsePairs, synPos, synAlphas, pPos, pAlpha } =
    useMemo(() => {
      const synPositions = new Float32Array(count * 6);
      const synAlphasArr = new Float32Array(count * 2);
      const pulsePositions = new Float32Array(count * 3);
      const pulseAlphasArr = new Float32Array(count);

      const pairs: Array<{
        a: number;
        b: number;
        life: number;
        maxLife: number;
        speed: number;
      }> = [];

      const totalParticles = cloudPositions ? cloudPositions.length / 3 : 5000;
      for (let i = 0; i < count; i++) {
        let pA = Math.floor(Math.random() * totalParticles);
        let pB = Math.floor(Math.random() * totalParticles);
        while (pA === pB) pB = Math.floor(Math.random() * totalParticles);

        pairs.push({
          a: pA,
          b: pB,
          life: Math.random(),
          maxLife: 1.0 + Math.random() * 2.0,
          speed: 0.3 + Math.random() * 0.7,
        });
      }

      const lGeo = new THREE.BufferGeometry();
      lGeo.setAttribute(
        "position",
        new THREE.BufferAttribute(synPositions, 3).setUsage(
          THREE.DynamicDrawUsage
        )
      );
      lGeo.setAttribute(
        "aAlpha",
        new THREE.BufferAttribute(synAlphasArr, 1).setUsage(
          THREE.DynamicDrawUsage
        )
      );

      const pGeo = new THREE.BufferGeometry();
      pGeo.setAttribute(
        "position",
        new THREE.BufferAttribute(pulsePositions, 3).setUsage(
          THREE.DynamicDrawUsage
        )
      );
      pGeo.setAttribute(
        "aAlpha",
        new THREE.BufferAttribute(pulseAlphasArr, 1).setUsage(
          THREE.DynamicDrawUsage
        )
      );

      return {
        lineGeo: lGeo,
        pulseGeo: pGeo,
        synapsePairs: pairs,
        synPos: synPositions,
        synAlphas: synAlphasArr,
        pPos: pulsePositions,
        pAlpha: pulseAlphasArr,
      };
    }, [count, cloudPositions]);

  const lineUniforms = useMemo(
    () => ({
      uColor: { value: color.clone() },
      uTime: { value: 0 },
    }),
    []
  );

  const pulseUniforms = useMemo(
    () => ({
      uColor: { value: color.clone() },
      uBoost: { value: 1.0 },
    }),
    []
  );

  const smoothThinking = useRef(0.0);

  useFrame((state, delta) => {
    const t = state.clock.getElapsedTime();
    const targetThinking = isThinking ? 1.0 : 0.0;
    smoothThinking.current += (targetThinking - smoothThinking.current) * (1 - Math.exp(-delta * 3.0));

    if (lineShaderMatRef.current) {
      lineShaderMatRef.current.uniforms.uColor.value.copy(color);
      lineShaderMatRef.current.uniforms.uTime.value = t;
    }
    if (pulseShaderMatRef.current) {
      pulseShaderMatRef.current.uniforms.uColor.value.copy(color);
      pulseShaderMatRef.current.uniforms.uBoost.value = 0.4 + 0.8 * smoothThinking.current;
    }

    if (!cloudPositions) return;

    const totalParticles = cloudPositions.length / 3;

    for (let i = 0; i < count; i++) {
      const syn = synapsePairs[i];
      syn.life += delta * syn.speed * (1.0 + 1.5 * smoothThinking.current);
      if (syn.life >= syn.maxLife) {
        syn.life = 0;
        syn.a = Math.floor(Math.random() * totalParticles);
        syn.b = Math.floor(Math.random() * totalParticles);
      }

      const pA = (syn.a % totalParticles) * 3;
      const pB = (syn.b % totalParticles) * 3;
      const o = i * 6;

      synPos[o] = cloudPositions[pA];
      synPos[o + 1] = cloudPositions[pA + 1];
      synPos[o + 2] = cloudPositions[pA + 2];

      synPos[o + 3] = cloudPositions[pB];
      synPos[o + 4] = cloudPositions[pB + 1];
      synPos[o + 5] = cloudPositions[pB + 2];

      const progress = syn.life / syn.maxLife;
      const fade = Math.sin(progress * Math.PI) * synapseDensity;
      synAlphas[i * 2] = fade;
      synAlphas[i * 2 + 1] = fade;

      // Impulso luminoso recorriendo la conexión
      const pi = i * 3;
      pPos[pi] = synPos[o] + (synPos[o + 3] - synPos[o]) * progress;
      pPos[pi + 1] = synPos[o + 1] + (synPos[o + 4] - synPos[o + 1]) * progress;
      pPos[pi + 2] = synPos[o + 2] + (synPos[o + 5] - synPos[o + 2]) * progress;
      pAlpha[i] = fade * (0.35 + 0.65 * smoothThinking.current);
    }

    lineGeo.attributes.position.needsUpdate = true;
    lineGeo.attributes.aAlpha.needsUpdate = true;
    pulseGeo.attributes.position.needsUpdate = true;
    pulseGeo.attributes.aAlpha.needsUpdate = true;
  });

  return (
    <group>
      <lineSegments ref={lineSegmentsRef} geometry={lineGeo}>
        <shaderMaterial
          ref={lineShaderMatRef}
          vertexShader={SynapseVertexShader}
          fragmentShader={SynapseFragmentShader}
          uniforms={lineUniforms}
          transparent
          depthWrite={false}
          blending={THREE.AdditiveBlending}
        />
      </lineSegments>

      <points ref={pulsePointsRef} geometry={pulseGeo}>
        <shaderMaterial
          ref={pulseShaderMatRef}
          vertexShader={PulseVertexShader}
          fragmentShader={PulseFragmentShader}
          uniforms={pulseUniforms}
          transparent
          depthWrite={false}
          blending={THREE.AdditiveBlending}
        />
      </points>
    </group>
  );
}
