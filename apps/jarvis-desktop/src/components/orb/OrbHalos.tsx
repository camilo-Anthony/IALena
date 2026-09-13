import React from "react";
import * as THREE from "three";

interface OrbHalosProps {
  color: THREE.Color;
  audioModulation?: number;
}

// Halos completamente eliminados — el orbe emite luz sólo desde su núcleo.
// Mantener el componente para compatibilidad con OrbScene sin causar errores de importación.
export function OrbHalos(_props: OrbHalosProps) {
  return null;
}
