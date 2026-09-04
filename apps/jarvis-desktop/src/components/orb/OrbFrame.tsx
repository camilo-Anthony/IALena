import React from "react";
import type { OrbState } from "../../types";
import { ORB_COLORS, getOrbStateProfile } from "./orbColors";

interface OrbFrameProps {
  state: OrbState;
}

/**
 * Marco HUD Geométrico y Óptico Puro JARVIS.
 * 100% libre de textos y letras: pura precisión visual aeroespacial,
 * brackets angulares con chaflán, reglas milimétricas, cruces de mira y resplandor cuántico.
 */
export function OrbFrame({ state }: OrbFrameProps) {
  const profileKey = getOrbStateProfile(state);
  const color = ORB_COLORS[profileKey];

  const isPulseActive =
    state === "listening" ||
    state === "thinking_fast" ||
    state === "speaking" ||
    state === "working_slow";

  return (
    <div className="absolute inset-0 pointer-events-none z-[5] overflow-hidden select-none">
      {/* ── 1. RESPLANDOR AMBIENTAL PERIMETRAL ── */}
      <div
        className="absolute inset-0 transition-opacity duration-1000 ease-out"
        style={{
          boxShadow: isPulseActive
            ? `inset 0 0 60px -15px ${color}25, inset 0 0 20px -5px ${color}35`
            : `inset 0 0 40px -20px ${color}12`,
          opacity: isPulseActive ? 0.9 : 0.4,
        }}
      />

      {/* ── 2. BORDES REFINADOS (1px óptico) ── */}
      <div
        className="absolute inset-[6px] border border-solid transition-colors duration-1000 ease-out"
        style={{ borderColor: `${color}28` }}
      />
      <div
        className="absolute inset-[10px] border border-dashed transition-colors duration-1000 ease-out"
        style={{ borderColor: `${color}10` }}
      />

      {/* ── 3. ESQUINAS TÁCTICAS DE PRECISIÓN (SIN LETRAS) ── */}

      {/* Esquina Superior Izquierda */}
      <div className="absolute top-[6px] left-[6px] flex flex-col">
        <div className="relative">
          <div
            className="h-[2px] transition-all duration-1000"
            style={{ width: 100, backgroundColor: color, boxShadow: `0 0 8px ${color}80` }}
          />
          <div
            className="w-[2px] transition-all duration-1000"
            style={{ height: 100, backgroundColor: color, boxShadow: `0 0 8px ${color}80` }}
          />
          <div
            className="absolute top-0 left-0 w-[5px] h-[5px] -translate-x-[2px] -translate-y-[2px] transition-all duration-1000"
            style={{ backgroundColor: color, boxShadow: `0 0 10px ${color}` }}
          />
          <svg className="absolute top-[3px] left-[3px] w-6 h-6" viewBox="0 0 24 24" fill="none">
            <path d="M 0 16 L 16 0" stroke={color} strokeWidth="1" strokeOpacity="0.4" />
          </svg>
          <div
            className="absolute top-[8px] left-[8px] h-[1px] transition-all duration-1000"
            style={{ width: 45, backgroundColor: color, opacity: 0.35 }}
          />
          <div
            className="absolute top-[8px] left-[8px] w-[1px] transition-all duration-1000"
            style={{ height: 45, backgroundColor: color, opacity: 0.35 }}
          />
        </div>
      </div>

      {/* Esquina Superior Derecha */}
      <div className="absolute top-[6px] right-[6px] flex flex-col items-end">
        <div className="relative">
          <div
            className="h-[2px] transition-all duration-1000"
            style={{ width: 100, backgroundColor: color, boxShadow: `0 0 8px ${color}80` }}
          />
          <div
            className="absolute right-0 top-0 w-[2px] transition-all duration-1000"
            style={{ height: 100, backgroundColor: color, boxShadow: `0 0 8px ${color}80` }}
          />
          <div
            className="absolute top-0 right-0 w-[5px] h-[5px] translate-x-[2px] -translate-y-[2px] transition-all duration-1000"
            style={{ backgroundColor: color, boxShadow: `0 0 10px ${color}` }}
          />
          <svg className="absolute top-[3px] right-[3px] w-6 h-6" viewBox="0 0 24 24" fill="none">
            <path d="M 24 16 L 8 0" stroke={color} strokeWidth="1" strokeOpacity="0.4" />
          </svg>
          <div
            className="absolute top-[8px] right-[8px] h-[1px] transition-all duration-1000"
            style={{ width: 45, backgroundColor: color, opacity: 0.35 }}
          />
          <div
            className="absolute top-[8px] right-[8px] w-[1px] transition-all duration-1000"
            style={{ height: 45, backgroundColor: color, opacity: 0.35 }}
          />
        </div>
      </div>

      {/* Esquina Inferior Izquierda */}
      <div className="absolute bottom-[6px] left-[6px] flex flex-col justify-end">
        <div className="relative">
          <div
            className="absolute bottom-0 left-0 w-[2px] transition-all duration-1000"
            style={{ height: 100, backgroundColor: color, boxShadow: `0 0 8px ${color}80` }}
          />
          <div
            className="absolute bottom-0 left-0 h-[2px] transition-all duration-1000"
            style={{ width: 100, backgroundColor: color, boxShadow: `0 0 8px ${color}80` }}
          />
          <div
            className="absolute bottom-0 left-0 w-[5px] h-[5px] -translate-x-[2px] translate-y-[2px] transition-all duration-1000"
            style={{ backgroundColor: color, boxShadow: `0 0 10px ${color}` }}
          />
          <svg className="absolute bottom-[3px] left-[3px] w-6 h-6" viewBox="0 0 24 24" fill="none">
            <path d="M 0 8 L 16 24" stroke={color} strokeWidth="1" strokeOpacity="0.4" />
          </svg>
          <div
            className="absolute bottom-[8px] left-[8px] h-[1px] transition-all duration-1000"
            style={{ width: 45, backgroundColor: color, opacity: 0.35 }}
          />
          <div
            className="absolute bottom-[8px] left-[8px] w-[1px] transition-all duration-1000"
            style={{ height: 45, backgroundColor: color, opacity: 0.35 }}
          />
        </div>
      </div>

      {/* Esquina Inferior Derecha */}
      <div className="absolute bottom-[6px] right-[6px] flex flex-col items-end justify-end">
        <div className="relative">
          <div
            className="absolute bottom-0 right-0 w-[2px] transition-all duration-1000"
            style={{ height: 100, backgroundColor: color, boxShadow: `0 0 8px ${color}80` }}
          />
          <div
            className="absolute bottom-0 right-0 h-[2px] transition-all duration-1000"
            style={{ width: 100, backgroundColor: color, boxShadow: `0 0 8px ${color}80` }}
          />
          <div
            className="absolute bottom-0 right-0 w-[5px] h-[5px] translate-x-[2px] translate-y-[2px] transition-all duration-1000"
            style={{ backgroundColor: color, boxShadow: `0 0 10px ${color}` }}
          />
          <svg className="absolute bottom-[3px] right-[3px] w-6 h-6" viewBox="0 0 24 24" fill="none">
            <path d="M 24 8 L 8 24" stroke={color} strokeWidth="1" strokeOpacity="0.4" />
          </svg>
          <div
            className="absolute bottom-[8px] right-[8px] h-[1px] transition-all duration-1000"
            style={{ width: 45, backgroundColor: color, opacity: 0.35 }}
          />
          <div
            className="absolute bottom-[8px] right-[8px] w-[1px] transition-all duration-1000"
            style={{ height: 45, backgroundColor: color, opacity: 0.35 }}
          />
        </div>
      </div>

      {/* ── 4. MIRA CENTRAL NORTE ── */}
      <div className="absolute top-[6px] left-1/2 -translate-x-1/2 flex items-center gap-1.5">
        <div className="w-10 h-[1px]" style={{ backgroundColor: color, opacity: 0.35 }} />
        <div className="w-[3px] h-[3px] rounded-full" style={{ backgroundColor: color }} />
        <div className="w-20 h-[2px]" style={{ backgroundColor: color, opacity: 0.7 }} />
        <div className="w-[3px] h-[3px] rounded-full" style={{ backgroundColor: color }} />
        <div className="w-10 h-[1px]" style={{ backgroundColor: color, opacity: 0.35 }} />
      </div>

      {/* ── 5. MIRA CENTRAL SUR ── */}
      <div className="absolute bottom-[6px] left-1/2 -translate-x-1/2 flex items-center gap-1.5">
        <div className="w-10 h-[1px]" style={{ backgroundColor: color, opacity: 0.35 }} />
        <div className="w-[3px] h-[3px] rounded-full" style={{ backgroundColor: color }} />
        <div className="w-20 h-[2px]" style={{ backgroundColor: color, opacity: 0.7 }} />
        <div className="w-[3px] h-[3px] rounded-full" style={{ backgroundColor: color }} />
        <div className="w-10 h-[1px]" style={{ backgroundColor: color, opacity: 0.35 }} />
      </div>

      {/* ── 6. NODOS CARDINALES LATERALES (OESTE Y ESTE) ── */}
      {/* Oeste */}
      <div className="absolute left-[6px] top-1/2 -translate-y-1/2 flex flex-col items-center gap-1.5">
        <div className="h-10 w-[1px]" style={{ backgroundColor: color, opacity: 0.35 }} />
        <div className="w-[3px] h-[3px] rounded-full" style={{ backgroundColor: color }} />
        <div className="h-20 w-[2px]" style={{ backgroundColor: color, opacity: 0.7 }} />
        <div className="w-[3px] h-[3px] rounded-full" style={{ backgroundColor: color }} />
        <div className="h-10 w-[1px]" style={{ backgroundColor: color, opacity: 0.35 }} />
      </div>

      {/* Este */}
      <div className="absolute right-[6px] top-1/2 -translate-y-1/2 flex flex-col items-center gap-1.5">
        <div className="h-10 w-[1px]" style={{ backgroundColor: color, opacity: 0.35 }} />
        <div className="w-[3px] h-[3px] rounded-full" style={{ backgroundColor: color }} />
        <div className="h-20 w-[2px]" style={{ backgroundColor: color, opacity: 0.7 }} />
        <div className="w-[3px] h-[3px] rounded-full" style={{ backgroundColor: color }} />
        <div className="h-10 w-[1px]" style={{ backgroundColor: color, opacity: 0.35 }} />
      </div>

      {/* ── 7. REGLAS MILIMÉTRICAS Y TICKS CALIBRADOS (SIN NÚMEROS) ── */}
      {/* Superior e inferior */}
      {[15, 25, 35, 65, 75, 85].map((pct) => (
        <React.Fragment key={`h-tick-${pct}`}>
          <div
            className="absolute top-[6px] h-[6px] w-[1px]"
            style={{ left: `${pct}%`, backgroundColor: color, opacity: pct % 2 === 0 ? 0.5 : 0.25 }}
          />
          <div
            className="absolute bottom-[6px] h-[6px] w-[1px]"
            style={{ left: `${pct}%`, backgroundColor: color, opacity: pct % 2 === 0 ? 0.5 : 0.25 }}
          />
        </React.Fragment>
      ))}

      {/* Ticks laterales */}
      {[20, 30, 40, 60, 70, 80].map((pct) => (
        <React.Fragment key={`v-tick-${pct}`}>
          <div
            className="absolute left-[6px] w-[6px] h-[1px]"
            style={{ top: `${pct}%`, backgroundColor: color, opacity: pct % 2 === 0 ? 0.5 : 0.25 }}
          />
          <div
            className="absolute right-[6px] w-[6px] h-[1px]"
            style={{ top: `${pct}%`, backgroundColor: color, opacity: pct % 2 === 0 ? 0.5 : 0.25 }}
          />
        </React.Fragment>
      ))}

      {/* Micro-cruces ópticas telescópicas (+) */}
      {[
        { top: "18%", left: "18%" },
        { top: "18%", right: "18%" },
        { bottom: "18%", left: "18%" },
        { bottom: "18%", right: "18%" },
      ].map((pos, idx) => (
        <div
          key={`cross-${idx}`}
          className="absolute flex items-center justify-center w-3 h-3 transition-opacity duration-1000"
          style={{ ...pos, opacity: isPulseActive ? 0.35 : 0.15 }}
        >
          <div className="absolute w-full h-[1px]" style={{ backgroundColor: color }} />
          <div className="absolute h-full w-[1px]" style={{ backgroundColor: color }} />
        </div>
      ))}
    </div>
  );
}
