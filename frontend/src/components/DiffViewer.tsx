import { Fragment } from "react";
import type { CallDiff } from "../types";

interface DiffViewerProps {
  callDiffs: CallDiff[];
}

function statusStyles(status: string): string {
  switch (status) {
    case "match":
      return "border-l-success/60";
    case "mismatch":
    case "arg_mismatch":
      return "border-l-warning/60";
    case "missing":
      return "border-l-failure/60";
    case "extra":
      return "border-l-accent/60";
    default:
      return "border-l-border";
  }
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return `"${value}"`;
  return JSON.stringify(value);
}

export function DiffViewer({ callDiffs }: DiffViewerProps) {
  if (callDiffs.length === 0) {
    return <p className="text-sm text-zinc-500">No differences to show.</p>;
  }

  return (
    <div className="space-y-3">
      {callDiffs.map((call, i) => (
        <div key={i} className={`border-l-4 bg-card border border-border rounded-r-lg pl-3 py-2 ${statusStyles(call.status)}`}>
          <div className="flex items-center justify-between">
            <span className="font-mono text-sm text-zinc-100">{call.function}(...)</span>
            <span className="text-xs uppercase tracking-wide text-zinc-500">{call.status.replace("_", " ")}</span>
          </div>
          {call.arg_diffs.length > 0 && (
            <div className="mt-2 grid grid-cols-[1fr_1fr_1fr] gap-x-2 gap-y-1 text-xs font-mono">
              <div className="text-zinc-500">arg</div>
              <div className="text-zinc-500">expected</div>
              <div className="text-zinc-500">actual</div>
              {call.arg_diffs.map((arg) => (
                <Fragment key={arg.key}>
                  <div className="text-zinc-300">{arg.key}</div>
                  <div
                    className={arg.status === "mismatch" || arg.status === "missing" ? "text-failure" : "text-zinc-400"}
                  >
                    {formatValue(arg.expected_value)}
                  </div>
                  <div
                    className={arg.status === "mismatch" || arg.status === "extra" ? "text-warning" : "text-zinc-400"}
                  >
                    {formatValue(arg.actual_value)}
                  </div>
                </Fragment>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
