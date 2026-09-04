import React, { useMemo } from "react";
import type { OrbState } from "../../types";
import { OrbFrame } from "./OrbFrame";
import { OrbSidebar } from "./OrbSidebar";

interface OrbHUDProps {
  state: OrbState;
}

export function OrbHUD({ state }: OrbHUDProps) {
  return (
    <>
      <OrbFrame state={state} />
      <OrbSidebar state={state} />
    </>
  );
}
