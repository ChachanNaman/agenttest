import { useCallback, useRef, useState } from "react";
import type { WsEvent } from "../types";

export type WsConnectionStatus = "idle" | "connecting" | "open" | "closed" | "error";

interface UseRunSocketOptions {
  onEvent: (event: WsEvent) => void;
}

export function useRunSocket({ onEvent }: UseRunSocketOptions) {
  const [status, setStatus] = useState<WsConnectionStatus>("idle");
  const socketRef = useRef<WebSocket | null>(null);

  const start = useCallback(
    (suiteFile: string) => {
      const protocol = window.location.protocol === "https:" ? "wss" : "ws";
      const socket = new WebSocket(`${protocol}://${window.location.host}/ws/run`);
      socketRef.current = socket;
      setStatus("connecting");

      socket.onopen = () => {
        setStatus("open");
        socket.send(JSON.stringify({ suite_file: suiteFile }));
      };

      socket.onmessage = (event: MessageEvent<string>) => {
        try {
          const parsed = JSON.parse(event.data) as WsEvent;
          onEvent(parsed);
        } catch {
          onEvent({ type: "error", message: "received malformed event from server" });
        }
      };

      socket.onerror = () => setStatus("error");
      socket.onclose = () => setStatus("closed");
    },
    [onEvent],
  );

  const stop = useCallback(() => {
    socketRef.current?.close();
    socketRef.current = null;
  }, []);

  return { status, start, stop };
}
