import { useEffect, useRef } from "react";
import { useJarvisStore } from "../store/jarvisStore";
import type { OrbState, TasksPayload, LogEntry } from "../types";

const WS_URL = "ws://127.0.0.1:8420/events";
const RECONNECT_MIN_MS = 1500;
const RECONNECT_MAX_MS = 15000;

/**
 * Hook que mantiene una conexión WebSocket con el backend JARVIS.
 * Despacha eventos al store Zustand automáticamente.
 * Auto-reconecta con backoff exponencial.
 */
export function useJarvisWS() {
  const setOrbState     = useJarvisStore((s) => s.setOrbState);
  const setTasks        = useJarvisStore((s) => s.setTasks);
  const appendLog       = useJarvisStore((s) => s.appendLog);
  const setWsConnected  = useJarvisStore((s) => s.setWsConnected);

  const retryDelay = useRef(RECONNECT_MIN_MS);
  const retryTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wsRef      = useRef<WebSocket | null>(null);
  const unmounted  = useRef(false);

  useEffect(() => {
    unmounted.current = false;

    function connect() {
      if (unmounted.current) return;

      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        retryDelay.current = RECONNECT_MIN_MS;
        setWsConnected(true);
        appendLog({
          ts: Date.now() / 1000,
          level: "INFO",
          source: "ws",
          message: "WebSocket conectado al kernel JARVIS",
        });
      };

      ws.onmessage = (evt) => {
        try {
          const msg = JSON.parse(evt.data as string);

          switch (msg.type) {
            case "state_change": {
              const state = msg.data?.orb_state as OrbState | undefined;
              if (state) setOrbState(state);
              break;
            }
            case "task_update": {
              setTasks(msg.data as TasksPayload);
              break;
            }
            case "log_entry": {
              appendLog(msg.data as LogEntry);
              break;
            }
            default:
              break;
          }
        } catch {
          // Ignorar mensajes mal formados
        }
      };

      ws.onclose = () => {
        setWsConnected(false);
        if (unmounted.current) return;

        appendLog({
          ts: Date.now() / 1000,
          level: "WARNING",
          source: "ws",
          message: `WebSocket desconectado. Reintentando en ${Math.round(retryDelay.current / 1000)}s…`,
        });

        retryTimer.current = setTimeout(() => {
          retryDelay.current = Math.min(retryDelay.current * 1.5, RECONNECT_MAX_MS);
          connect();
        }, retryDelay.current);
      };

      ws.onerror = () => {
        ws.close();
      };
    }

    connect();

    return () => {
      unmounted.current = true;
      if (retryTimer.current) clearTimeout(retryTimer.current);
      wsRef.current?.close();
      setWsConnected(false);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
}
