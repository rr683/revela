import { useEffect, useRef, useCallback } from "react";
import type { Job } from "../types";

interface UseJobsWebSocketOptions {
  onJobUpdate: (job: Job) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
}

const WS_BASE =
  import.meta.env.VITE_WS_URL ||
  `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}`;

export default function useJobsWebSocket({
  onJobUpdate,
  onConnect,
  onDisconnect,
}: UseJobsWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const mountedRef = useRef(true);

  const connect = useCallback(() => {
    if (!mountedRef.current) return;
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    try {
      const ws = new WebSocket(`${WS_BASE}/ws/jobs`);

      ws.onopen = () => {
        onConnect?.();
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "job_update" && data.job) {
            onJobUpdate(data.job);
          }
        } catch {
          // ignore malformed messages
        }
      };

      ws.onclose = () => {
        wsRef.current = null;
        onDisconnect?.();
        if (mountedRef.current) {
          reconnectTimer.current = setTimeout(connect, 3000);
        }
      };

      ws.onerror = () => {
        ws.close();
      };

      wsRef.current = ws;
    } catch {
      if (mountedRef.current) {
        reconnectTimer.current = setTimeout(connect, 3000);
      }
    }
  }, [onJobUpdate, onConnect, onDisconnect]);

  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [connect]);
}
