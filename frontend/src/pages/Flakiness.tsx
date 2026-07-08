import { useEffect, useState } from "react";
import { apiGet } from "../hooks/useApi";
import type { FlakinessRow, RunSummary } from "../types";

const GAUGE_RADIUS = 26;
const GAUGE_STROKE = 6;
const ARC_SPAN_DEGREES = 270;
const ARC_CIRCUMFERENCE = 2 * Math.PI * GAUGE_RADIUS * (ARC_SPAN_DEGREES / 360);

function gaugeColor(score: number): string {
  if (score < 0.15) return "#22c55e";
  if (score < 0.4) return "#f59e0b";
  return "#ef4444";
}

function recommendedAction(score: number): string {
  if (score < 0.15) return "No action needed — reliable";
  if (score < 0.4) return "Lower temperature or tighten the prompt";
  return "Rewrite prompt or add few-shot examples";
}

function FlakinessGauge({ score }: { score: number }) {
  const color = gaugeColor(score);
  const offset = ARC_CIRCUMFERENCE * (1 - score);
  const size = (GAUGE_RADIUS + GAUGE_STROKE) * 2;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle
        cx={size / 2}
        cy={size / 2}
        r={GAUGE_RADIUS}
        fill="none"
        stroke="#1e1e2e"
        strokeWidth={GAUGE_STROKE}
        strokeDasharray={`${ARC_CIRCUMFERENCE} ${2 * Math.PI * GAUGE_RADIUS}`}
        strokeDashoffset={0}
        strokeLinecap="round"
        transform={`rotate(135 ${size / 2} ${size / 2})`}
      />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={GAUGE_RADIUS}
        fill="none"
        stroke={color}
        strokeWidth={GAUGE_STROKE}
        strokeDasharray={ARC_CIRCUMFERENCE}
        strokeDashoffset={offset}
        strokeLinecap="round"
        transform={`rotate(135 ${size / 2} ${size / 2})`}
        style={{ transition: "stroke-dashoffset 300ms ease" }}
      />
      <text x={size / 2} y={size / 2 + 4} textAnchor="middle" fontSize={11} fill="#e4e4e7" className="font-mono">
        {score.toFixed(2)}
      </text>
    </svg>
  );
}

export function Flakiness() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [suite, setSuite] = useState("");
  const [rows, setRows] = useState<FlakinessRow[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    apiGet<RunSummary[]>("/runs").then(setRuns).catch(() => setRuns([]));
  }, []);

  const suites = Array.from(new Set(runs.map((r) => r.suite_name)));

  useEffect(() => {
    if (suites.length > 0 && !suite) setSuite(suites[0]);
  }, [suites, suite]);

  useEffect(() => {
    if (!suite) return;
    setLoading(true);
    apiGet<FlakinessRow[]>(`/flakiness/${encodeURIComponent(suite)}`)
      .then((data) => setRows([...data].sort((a, b) => b.flakiness_score - a.flakiness_score)))
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  }, [suite]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-zinc-100">Flakiness</h1>
        <p className="text-zinc-500 mt-1">Tests ranked by how much their pass rate fluctuates across runs.</p>
      </div>

      <select
        value={suite}
        onChange={(e) => setSuite(e.target.value)}
        className="bg-card border border-border rounded-lg px-3 py-2 text-sm text-zinc-100"
      >
        {suites.length === 0 && <option value="">No suites run yet</option>}
        {suites.map((s) => (
          <option key={s} value={s}>
            {s}
          </option>
        ))}
      </select>

      {loading ? (
        <p className="text-zinc-500 text-sm">Loading...</p>
      ) : rows.length === 0 ? (
        <p className="text-zinc-500 text-sm">No run history for this suite yet.</p>
      ) : (
        <div className="grid gap-3">
          {rows.map((row) => (
            <div
              key={row.test_name}
              className="bg-card border border-border rounded-xl p-4 flex items-center gap-5"
            >
              <FlakinessGauge score={row.flakiness_score} />
              <div className="flex-1 min-w-0">
                <h3 className="font-medium text-zinc-100 truncate">{row.test_name}</h3>
                <p className="text-sm text-zinc-500 font-mono mt-1">
                  current: {(row.current_pass_rate * 100).toFixed(1)}% · variance:{" "}
                  {row.pass_rate_variance.toFixed(4)} · n={row.sample_size}
                </p>
                <p className="text-xs mt-1" style={{ color: gaugeColor(row.flakiness_score) }}>
                  {recommendedAction(row.flakiness_score)}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
