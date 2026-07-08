import { useEffect, useMemo, useState } from "react";
import { LineChart } from "../components/LineChart";
import { apiGet } from "../hooks/useApi";
import type { HistoryPoint, RunSummary } from "../types";

function formatDate(iso: string): string {
  const d = new Date(iso);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

function flakinessLabel(score: number): { label: string; color: string } {
  if (score < 0.15) return { label: "Stable", color: "text-success" };
  if (score < 0.4) return { label: "Somewhat flaky", color: "text-warning" };
  return { label: "Flaky", color: "text-failure" };
}

export function History() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [suite, setSuite] = useState<string>("");
  const [testName, setTestName] = useState<string>("");
  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    apiGet<RunSummary[]>("/runs").then(setRuns).catch(() => setRuns([]));
  }, []);

  const suites = useMemo(() => Array.from(new Set(runs.map((r) => r.suite_name))), [runs]);
  const testsForSuite = useMemo(
    () => Array.from(new Set(runs.filter((r) => r.suite_name === suite).map((r) => r.test_name))),
    [runs, suite],
  );

  useEffect(() => {
    if (suites.length > 0 && !suite) setSuite(suites[0]);
  }, [suites, suite]);

  useEffect(() => {
    if (testsForSuite.length > 0 && !testsForSuite.includes(testName)) {
      setTestName(testsForSuite[0]);
    }
  }, [testsForSuite, testName]);

  useEffect(() => {
    if (!suite || !testName) return;
    setLoading(true);
    apiGet<HistoryPoint[]>(`/history/${encodeURIComponent(suite)}/${encodeURIComponent(testName)}`)
      .then(setHistory)
      .catch(() => setHistory([]))
      .finally(() => setLoading(false));
  }, [suite, testName]);

  const passRatePoints = history.map((h) => ({
    label: formatDate(h.started_at),
    value: h.pass_rate,
    meetsThreshold: h.meets_threshold === 1,
  }));

  const latencies = history.map((h) => h.avg_latency_ms ?? 0);
  const maxLatency = Math.max(1, ...latencies);
  const latencyPoints = history.map((h) => ({
    label: formatDate(h.started_at),
    value: h.avg_latency_ms ?? 0,
  }));

  const latestFlakiness = history.length > 0 ? history[history.length - 1].flakiness_score : null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-zinc-100">History</h1>
        <p className="text-zinc-500 mt-1">Pass-rate and latency trends across past runs.</p>
      </div>

      <div className="flex gap-3">
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
        <select
          value={testName}
          onChange={(e) => setTestName(e.target.value)}
          className="bg-card border border-border rounded-lg px-3 py-2 text-sm text-zinc-100"
        >
          {testsForSuite.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        {latestFlakiness !== null && (
          <span className={`ml-auto self-center text-xs px-3 py-1.5 rounded-full border border-border font-mono ${flakinessLabel(latestFlakiness).color}`}>
            {flakinessLabel(latestFlakiness).label} ({latestFlakiness.toFixed(2)})
          </span>
        )}
      </div>

      {loading ? (
        <p className="text-zinc-500 text-sm">Loading...</p>
      ) : (
        <div className="space-y-6">
          <div className="bg-card border border-border rounded-xl p-4">
            <h2 className="text-sm font-medium text-zinc-400 mb-3">Pass rate over time</h2>
            <LineChart data={passRatePoints} threshold={history[history.length - 1]?.threshold} color="#6366f1" />
          </div>
          <div className="bg-card border border-border rounded-xl p-4">
            <h2 className="text-sm font-medium text-zinc-400 mb-3">Average latency over time</h2>
            <LineChart
              data={latencyPoints}
              color="#22c55e"
              yMax={maxLatency}
              valueFormatter={(v) => `${v.toFixed(0)}ms`}
            />
          </div>
        </div>
      )}
    </div>
  );
}
