import { useEffect, useRef } from "react";
import type { WsEvent } from "../types";

interface LiveFeedProps {
  events: WsEvent[];
}

function describeEvent(event: WsEvent): { text: string; color: string } {
  switch (event.type) {
    case "run_started":
      return { text: `Run started — ${event.suite} (${event.total_tests} tests)`, color: "text-accent" };
    case "test_started":
      return { text: `▸ ${event.test_name} — starting ${event.runs} runs`, color: "text-zinc-300" };
    case "iteration_complete":
      return {
        text: `  #${event.iteration} ${event.passed ? "passed" : "failed"} — running rate ${(event.current_pass_rate * 100).toFixed(0)}%`,
        color: event.passed ? "text-success" : "text-failure",
      };
    case "test_complete":
      return { text: `✓ ${event.test_name} complete — ${event.verdict}`, color: event.meets_threshold ? "text-success" : "text-failure" };
    case "run_complete":
      return { text: `Run complete — ${event.passed}/${event.total} tests passed`, color: "text-accent" };
    case "error":
      return { text: `Error: ${event.message}`, color: "text-failure" };
    default:
      return { text: "unknown event", color: "text-zinc-500" };
  }
}

export function LiveFeed({ events }: LiveFeedProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [events.length]);

  return (
    <div
      ref={scrollRef}
      className="bg-card border border-border rounded-xl p-3 h-64 overflow-y-auto font-mono text-xs space-y-0.5"
    >
      {events.length === 0 && <p className="text-zinc-600">Waiting for a run to start...</p>}
      {events.map((event, i) => {
        const { text, color } = describeEvent(event);
        return (
          <div key={i} className={color}>
            {text}
          </div>
        );
      })}
    </div>
  );
}
