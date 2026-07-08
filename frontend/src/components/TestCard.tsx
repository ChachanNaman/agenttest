import { useState } from "react";
import type { LiveTestState } from "../types";

interface TestCardProps {
  state: LiveTestState;
}

const RING_RADIUS = 22;
const RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS;

function statusColor(passRate: number): string {
  if (passRate >= 0.85) return "#22c55e";
  if (passRate >= 0.6) return "#f59e0b";
  return "#ef4444";
}

function ProgressRing({ progress, passRate }: { progress: number; passRate: number }) {
  const color = statusColor(passRate);
  const offset = RING_CIRCUMFERENCE * (1 - progress);
  return (
    <svg width={56} height={56} className="shrink-0">
      <circle cx={28} cy={28} r={RING_RADIUS} fill="none" stroke="#1e1e2e" strokeWidth={5} />
      <circle
        cx={28}
        cy={28}
        r={RING_RADIUS}
        fill="none"
        stroke={color}
        strokeWidth={5}
        strokeLinecap="round"
        strokeDasharray={RING_CIRCUMFERENCE}
        strokeDashoffset={offset}
        transform="rotate(-90 28 28)"
        style={{ transition: "stroke-dashoffset 300ms ease" }}
      />
      <text x={28} y={32} textAnchor="middle" fontSize={11} fill="#e4e4e7" className="font-mono">
        {Math.round(progress * 100)}%
      </text>
    </svg>
  );
}

export function TestCard({ state }: TestCardProps) {
  const [expanded, setExpanded] = useState(false);
  const progress = state.runs > 0 ? state.completedIterations / state.runs : 0;
  const isComplete = state.status === "complete";
  const passRate = isComplete ? (state.finalPassRate ?? 0) : state.currentPassRate;

  const badgeColor = isComplete
    ? state.meetsThreshold
      ? "bg-success/15 text-success border-success/30"
      : "bg-failure/15 text-failure border-failure/30"
    : "bg-accent/15 text-accent border-accent/30";

  const failedIterations = state.iterationOutcomes
    .map((passed, i) => ({ passed, i }))
    .filter((x) => !x.passed);

  return (
    <div className="bg-card border border-border rounded-xl p-4">
      <div className="flex items-center gap-4">
        <ProgressRing progress={progress} passRate={passRate} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <h3 className="font-medium text-zinc-100 truncate">{state.test_name}</h3>
            <span className={`text-xs px-2 py-0.5 rounded-full border font-mono ${badgeColor}`}>
              {isComplete ? (state.meetsThreshold ? "PASS" : "FAIL") : "RUNNING"}
            </span>
          </div>
          <p className="text-sm text-zinc-500 font-mono mt-1">
            {state.completedIterations}/{state.runs} iterations
            {" · "}
            {(passRate * 100).toFixed(1)}% pass rate
          </p>
          {isComplete && state.finalVerdict && (
            <p className="text-xs text-zinc-500 mt-1">{state.finalVerdict}</p>
          )}
        </div>
      </div>

      {failedIterations.length > 0 && (
        <div className="mt-3 border-t border-border pt-2">
          <button
            onClick={() => setExpanded((e) => !e)}
            className="text-xs text-zinc-400 hover:text-zinc-200 flex items-center gap-1"
          >
            <span>{expanded ? "▾" : "▸"}</span>
            {failedIterations.length} failed iteration{failedIterations.length === 1 ? "" : "s"}
          </button>
          {expanded && (
            <div className="mt-2 flex flex-wrap gap-1">
              {state.iterationOutcomes.map((passed, i) => (
                <span
                  key={i}
                  title={`iteration ${i + 1}: ${passed ? "passed" : "failed"}`}
                  className={`w-4 h-4 rounded-sm ${passed ? "bg-success/40" : "bg-failure"}`}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
