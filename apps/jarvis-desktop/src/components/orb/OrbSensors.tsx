import React, { useRef, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

interface OrbSensorsProps {
  color: string;
  speed: number;
  count?: number;
}

/**
 * Componente que renderiza hebras curvas (sensores táctiles) distribuidas
 * uniformemente en la superficie del orbe usando la espiral de Fibonacci.
 * Flotan con un vaivén (sway) asimétrico de ruido.
 */
export function OrbSensors({ color, speed, count = 50 }: OrbSensorsProps) {
  const groupRef = useRef<THREE.Group>(null);
  const sensorColor = useRef(new THREE.Color(color));

  // Generar puntos de Fibonacci estáticos en la esfera
  const linesData = useMemo(() => {
    const points: { start: THREE.Vector3; control: THREE.Vector3; end: THREE.Vector3 }[] = [];
    const phi = Math.PI * (3.0 - Math.sqrt(5.0)); // Ángulo áureo

    for (let i = 0; i < count; i++) {
      const y = 1.0 - (i / (count - 1)) * 2.0; // De 1 a -1
      const radius = Math.sqrt(1.0 - y * y); // Radio en la altura y
      const theta = phi * i;

      const x = Math.cos(theta) * radius;
      const z = Math.sin(theta) * radius;

      // Punto inicial en la superficie de la esfera de radio 1.1
      const start = new THREE.Vector3(x, y, z).multiplyScalar(1.1);

      // Dirección normal hacia afuera
      const normal = start.clone().normalize();

      // Pelo largo y sutilmente curvado hacia afuera
      const end = start.clone().add(normal.clone().multiplyScalar(0.28));

      // Punto de control para curva cuadrática Bezier (para dar curva natural)
      const tangent = new THREE.Vector3(-z, 0, x).normalize(); // Dirección transversal
      const control = start.clone().add(normal.clone().multiplyScalar(0.14)).add(tangent.multiplyScalar(0.1));

      points.push({ start, control, end });
    }

    return points;
  }, [count]);

  useFrame((state) => {
    const t = state.clock.getElapsedTime();
    sensorColor.current.set(color);

    if (groupRef.current) {
      // Rotación global sutil sincronizada
      groupRef.current.rotation.y = t * 0.05;

      // Animar cada línea con sway dinámico modificando su rotación individual o aplicando un ruido a las hebras
      groupRef.current.children.forEach((child, idx) => {
        const line = child as THREE.Line;
        const mat = line.material as THREE.LineBasicMaterial;
        mat.color.lerp(sensorColor.current, 0.05);

        // Sway no lineal usando fases desfasadas por índice
        const offsetPhase = idx * 0.2;
        const swayX = Math.sin(t * 1.5 * speed + offsetPhase) * 0.08;
        const swayZ = Math.cos(t * 1.1 * speed + offsetPhase) * 0.08;

        line.rotation.x = swayX;
        line.rotation.z = swayZ;
      });
    }
  });

  return (
    <group ref={groupRef}>
      {linesData.map((pt, idx) => {
        // Crear geometría de curva cuadrática
        const curve = new THREE.QuadraticBezierCurve3(pt.start, pt.control, pt.end);
        const points = curve.getPoints(12);
        const geometry = new THREE.BufferGeometry().setFromPoints(points);

        return (
          <lineSegments key={idx} geometry={geometry}>
            <lineBasicMaterial color={color} transparent opacity={0.45} linewidth={1} />
          </lineSegments>
        );
      })}
    </group>
  );
}
