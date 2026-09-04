import type { OrbState } from "../../types";

export const ORB_COLORS: Record<string, string> = {
  reposo: "#0A84FF",      // Azul cuántico luminoso y equilibrado
  escuchando: "#FFC700",  // Oro cálido electromagnético brillante
  pensando: "#A855F7",    // Ultravioleta cósmico vibrante
  hablando: "#00E5FF",    // Cyan neón cristalino de alta frecuencia
  ejecutando: "#FF1744",  // Carmesí láser de alta energía
};

export function getOrbStateProfile(state: OrbState | string): string {
  switch (state) {
    case "listening":
    case "active":
    case "escuchando":
      return "escuchando";
    case "speaking":
    case "delivery_waiting":
    case "hablando":
      return "hablando";
    case "thinking_fast":
    case "thinking":
    case "confirmation_pending":
    case "reconnecting":
    case "pensando":
      return "pensando";
    case "working_slow":
    case "executing":
    case "error":
    case "ejecutando":
      return "ejecutando";
    case "dormant":
    case "idle":
    case "reposo":
    default:
      return "reposo";
  }
}
