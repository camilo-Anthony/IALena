import { useEffect, useRef } from "react";

/**
 * Hook de Repulsión Magnética de la Ventana Física en el Escritorio.
 * La ventana de Tauri se mueve como un imán repelido por el cursor.
 */
export function useWindowEvasion(enabled = true) {
  const posRef = useRef<{ x: number; y: number } | null>(null);
  const velRef = useRef({ vx: 0, vy: 0 });
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!enabled) return;

    const isTauri =
      typeof window !== "undefined" &&
      ("__TAURI_INTERNALS__" in window || "__TAURI__" in window);

    if (!isTauri) {
      console.log("[WindowEvasion] No es Tauri, desactivado.");
      return;
    }

    console.log("[WindowEvasion] Iniciando...");

    let active = true;
    let tauriWindow: any = null;
    let tauriInvoke: any = null;
    let PhysicalPosition: any = null;

    const WIN_SIZE = 400;
    const MAGNETIC_RADIUS = 280;
    const MAX_SPEED = 48;

    // Inicializar Tauri y arrancar el loop
    (async () => {
      try {
        const winMod = await import("@tauri-apps/api/window");
        const coreMod = await import("@tauri-apps/api/core");
        const dpiMod = await import("@tauri-apps/api/dpi");

        if (!active) return;

        tauriWindow = winMod.getCurrentWindow();
        tauriInvoke = coreMod.invoke;
        PhysicalPosition = dpiMod.PhysicalPosition;

        // Click-through total
        await tauriWindow.setIgnoreCursorEvents(true);
        console.log("[WindowEvasion] Click-through activado.");

        // Posición inicial de la ventana
        const initPos = await tauriWindow.outerPosition();
        posRef.current = { x: initPos.x, y: initPos.y };
        console.log("[WindowEvasion] Posición inicial:", posRef.current);

        // Test: verificar que get_cursor_position funciona
        try {
          const testCursor = await tauriInvoke("get_cursor_position");
          console.log("[WindowEvasion] Cursor test:", testCursor);
        } catch (e) {
          console.error("[WindowEvasion] Error en get_cursor_position:", e);
        }

        // ── LOOP DE FÍSICA (setInterval a 60fps) ──
        intervalRef.current = setInterval(async () => {
          if (!active || !posRef.current) return;

          try {
            // 1. Obtener posición global del cursor
            const cursor = await tauriInvoke("get_cursor_position");
            if (!cursor || !Array.isArray(cursor) || cursor.length !== 2) return;

            const [cx, cy] = cursor;
            const centerX = posRef.current.x + WIN_SIZE / 2;
            const centerY = posRef.current.y + WIN_SIZE / 2;

            const dx = centerX - cx;
            const dy = centerY - cy;
            const dist = Math.sqrt(dx * dx + dy * dy);

            // 2. Fuerza de repulsión magnética
            if (dist < MAGNETIC_RADIUS && dist > 0.5) {
              const intensity = Math.pow((MAGNETIC_RADIUS - dist) / MAGNETIC_RADIUS, 1.3);
              const force = intensity * 28.0;
              const nx = dx / dist;
              const ny = dy / dist;

              velRef.current.vx += nx * force;
              velRef.current.vy += ny * force;

              // Limitar velocidad
              const spd = Math.sqrt(velRef.current.vx ** 2 + velRef.current.vy ** 2);
              if (spd > MAX_SPEED) {
                velRef.current.vx = (velRef.current.vx / spd) * MAX_SPEED;
                velRef.current.vy = (velRef.current.vy / spd) * MAX_SPEED;
              }
            }

            // 3. Integrar posición con inercia
            const spd = Math.sqrt(velRef.current.vx ** 2 + velRef.current.vy ** 2);
            if (spd > 0.1) {
              let nextX = posRef.current.x + velRef.current.vx;
              let nextY = posRef.current.y + velRef.current.vy;

              // Límites del monitor
              const screenW = window.screen.availWidth || 1920;
              const screenH = window.screen.availHeight || 1080;
              const minX = 5;
              const maxX = Math.max(minX, screenW - WIN_SIZE - 5);
              const minY = 5;
              const maxY = Math.max(minY, screenH - WIN_SIZE - 5);

              // Rebote elástico
              if (nextX <= minX) { nextX = minX; velRef.current.vx = Math.abs(velRef.current.vx) * 0.7; }
              else if (nextX >= maxX) { nextX = maxX; velRef.current.vx = -Math.abs(velRef.current.vx) * 0.7; }
              if (nextY <= minY) { nextY = minY; velRef.current.vy = Math.abs(velRef.current.vy) * 0.7; }
              else if (nextY >= maxY) { nextY = maxY; velRef.current.vy = -Math.abs(velRef.current.vy) * 0.7; }

              posRef.current.x = nextX;
              posRef.current.y = nextY;

              // Fricción (se queda donde fue empujada)
              velRef.current.vx *= 0.91;
              velRef.current.vy *= 0.91;

              // 4. Mover la ventana física
              await tauriWindow.setPosition(
                new PhysicalPosition(Math.round(nextX), Math.round(nextY))
              );
            }
          } catch {
            // Ignorar errores de frame individual
          }
        }, 16); // ~60fps

        console.log("[WindowEvasion] Loop de física iniciado.");

      } catch (err) {
        console.error("[WindowEvasion] Error de inicialización:", err);
      }
    })();

    return () => {
      active = false;
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [enabled]);
}
