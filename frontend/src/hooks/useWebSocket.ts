import { useEffect, useRef } from "react";
import { getWsUrl } from "../lib/api";
import { getRun, getResults } from "../lib/api";
import { useHealStore } from "../stores/useHealStore";
import type { WSEvent } from "../types";

export function useWebSocket(runId: string | null) {
  const wsRef = useRef<WebSocket | null>(null);
  const retriesRef = useRef(0);
  const addWsEvent = useHealStore((s) => s.addWsEvent);
  const setRunStatus = useHealStore((s) => s.setRunStatus);
  const setResults = useHealStore((s) => s.setResults);
  const setError = useHealStore((s) => s.setError);

  useEffect(() => {
    if (!runId) return;

    let closed = false;

    function connect() {
      if (closed) return;
      const url = getWsUrl(runId!);
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        retriesRef.current = 0;
      };

      ws.onmessage = (e) => {
        try {
          const event: WSEvent = JSON.parse(e.data);
          if (!event.event_type) return; // skip acks
          addWsEvent(event);

          if (event.event_type === "complete" || event.event_type === "error") {
            // Refetch final state
            getRun(runId!).then(setRunStatus).catch(() => {});
            getResults(runId!).then(setResults).catch(() => {});
            if (event.event_type === "error") {
              setError(event.message);
            }
          }
        } catch {
          // ignore parse errors
        }
      };

      ws.onclose = () => {
        if (closed) return;
        // Exponential backoff reconnect
        const delay = Math.min(1000 * 2 ** retriesRef.current, 30000);
        retriesRef.current++;
        setTimeout(connect, delay);
      };

      ws.onerror = () => {
        ws.close();
      };
    }

    connect();

    // Also poll status periodically as fallback
    const pollId = setInterval(() => {
      getRun(runId).then((s) => {
        setRunStatus(s);
        if (s.status === "completed" || s.status === "failed") {
          getResults(runId).then(setResults).catch(() => {});
        }
      }).catch(() => {});
    }, 5000);

    return () => {
      closed = true;
      clearInterval(pollId);
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [runId, addWsEvent, setRunStatus, setResults, setError]);
}
