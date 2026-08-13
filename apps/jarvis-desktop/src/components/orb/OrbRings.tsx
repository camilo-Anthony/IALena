import React, { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

interface OrbRingsProps {
  color: string;
  speed: number;
}

export function OrbRings({ color, speed }: OrbRingsProps) {
  const groupRef = useRef<THREE.Group>(null);
  const ring1Ref = useRef<THREE.Mesh>(null);
  const ring2Ref = useRef<THREE.Mesh>(null);
  const ring3Ref = useRef<THREE.Mesh>(null);

  const ringColor = useRef(new THREE.Color(color));

  useFrame((state) => {
    const t = state.clock.getElapsedTime();
    ringColor.current.set(color);

    // Actualizar colores del material directamente
    [ring1Ref, ring2Ref, ring3Ref].forEach((ref) => {
      if (ref.current) {
        const mat = ref.current.material as THREE.MeshBasicMaterial;
        mat.color.lerp(ringColor.current, 0.05);
      }
    });

    // Rotaciones diferenciales para look giroscópico complejo
    if (ring1Ref.current) {
      ring1Ref.current.rotation.x = t * 0.4 * speed;
      ring1Ref.current.rotation.y = t * 0.2;
    }
    if (ring2Ref.current) {
      ring2Ref.current.rotation.y = -t * 0.6 * speed;
      ring2Ref.current.rotation.z = t * 0.3;
    }
    if (ring3Ref.current) {
      ring3Ref.current.rotation.z = t * 0.2 * speed;
      ring3Ref.current.rotation.x = -t * 0.3;
    }
  });

  return (
    <group ref={groupRef}>
      {/* Anillo Giroscópico Exterior 1 */}
      <mesh ref={ring1Ref}>
        <torusGeometry args={[1.7, 0.012, 8, 100]} />
        <meshBasicMaterial color={color} transparent opacity={0.3} wireframe />
      </mesh>

      {/* Anillo Giroscópico 2 */}
      <mesh ref={ring2Ref} rotation={[Math.PI / 4, Math.PI / 4, 0]}>
        <torusGeometry args={[1.5, 0.01, 8, 100]} />
        <meshBasicMaterial color={color} transparent opacity={0.25} wireframe />
      </mesh>

      {/* Anillo Giroscópico Interior 3 */}
      <mesh ref={ring3Ref} rotation={[Math.PI / 2, 0, Math.PI / 4]}>
        <torusGeometry args={[1.3, 0.008, 8, 80]} />
        <meshBasicMaterial color={color} transparent opacity={0.4} wireframe />
      </mesh>
    </group>
  );
}
