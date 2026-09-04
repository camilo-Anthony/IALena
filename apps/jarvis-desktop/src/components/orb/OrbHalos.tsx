import React, { useRef, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { createGlowTexture } from "./OrbTextures";

interface OrbHalosProps {
  color: THREE.Color;
  audioModulation?: number;
}

export function OrbHalos({ color, audioModulation = 0 }: OrbHalosProps) {
  const closeSpriteRef = useRef<THREE.Sprite>(null);
  const midSpriteRef = useRef<THREE.Sprite>(null);
  const outerSpriteRef = useRef<THREE.Sprite>(null);

  const texSoftGlow = useMemo(
    () => createGlowTexture(256, "rgba(255,255,255,0.7)", "rgba(255,255,255,0.0)"),
    []
  );
  const texHaloFar = useMemo(
    () => createGlowTexture(512, "rgba(255,255,255,0.35)", "rgba(255,255,255,0.0)"),
    []
  );

  useFrame((state) => {
    const time = state.clock.getElapsedTime();
    const haloBreath =
      1.0 +
      0.04 * Math.sin(time * 0.8) +
      0.02 * Math.sin(time * 1.7) +
      audioModulation * 0.15;

    if (closeSpriteRef.current) {
      const s = 3.2 * haloBreath;
      closeSpriteRef.current.scale.set(s, s, s);
      const mat = closeSpriteRef.current.material as THREE.SpriteMaterial;
      mat.color.copy(color);
    }

    if (midSpriteRef.current) {
      const s = 5.6 * haloBreath;
      midSpriteRef.current.scale.set(s, s, s);
      const mat = midSpriteRef.current.material as THREE.SpriteMaterial;
      mat.color.copy(color);
    }

    if (outerSpriteRef.current) {
      const s = 9.2 * haloBreath;
      outerSpriteRef.current.scale.set(s, s, s);
      const mat = outerSpriteRef.current.material as THREE.SpriteMaterial;
      mat.color.copy(color);
    }
  });

  return (
    <group>
      {/* 1. Halo Cercano Intenso */}
      <sprite ref={closeSpriteRef} visible={true}>
        <spriteMaterial
          map={texSoftGlow}
          color={color}
          blending={THREE.AdditiveBlending}
          transparent
          opacity={0.25}
          depthWrite={false}
        />
      </sprite>

      {/* 2. Halo Intermedio */}
      <sprite ref={midSpriteRef} visible={true}>
        <spriteMaterial
          map={texHaloFar}
          color={color}
          blending={THREE.AdditiveBlending}
          transparent
          opacity={0.08}
          depthWrite={false}
        />
      </sprite>

      {/* 3. Halo Difuso Exterior */}
      <sprite ref={outerSpriteRef} visible={false}>
        <spriteMaterial
          map={texHaloFar}
          color={color}
          blending={THREE.AdditiveBlending}
          transparent
          opacity={0.03}
          depthWrite={false}
        />
      </sprite>
    </group>
  );
}
