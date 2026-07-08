import { useMemo, useState } from "react";
import { BarChart } from "../components/BarChart";
import { apiPost } from "../hooks/useApi";
import type { BenchmarkModelRow, BenchmarkResponse } from "../types";

type SortKey = "model" | "pass_rate" | "avg_latency_ms";

const DEFAULT_MODELS = "llama-3.3-70b-versatile,claude-haiku-4-5,gpt-4o-mini";

function estimatedCostPer100Runs(model: string): number {
  const lowered = model.toLowerCase();
  if (lowered.includes("llama") || lowered.includes("mixtral") || lowered.includes("gemma")) return 0.0;
  if (lowered.includes("haiku")) return 0.08;
  if (lowered.includes("claude")) return 0.9;
  if (lowered.includes("gpt-4o-mini")) return 0.12;
  if (lowered.includes("gpt")) return 1.5;
  return 0.0;
}

function argAccuracy(row: BenchmarkModelRow): number {
  if (row.tests.length === 0) return 0;
  return row.tests.reduce((sum, t) => sum + t.pass_rate, 0) / row.tests.length;
}

export function Benchmark() {
  const [suiteFile, setSuiteFile] = useState("tests/examples/booking.yaml");
  const [modelsInput, setModelsInput] = useState(DEFAULT_MODELS);
  const [runs, setRuns] = useState("");
  const [result, setResult] = useState<BenchmarkResponse | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("pass_rate");
  const [sortDesc, setSortDesc] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleBenchmark = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const models = modelsInput.split(",").map((m) => m.trim()).filter(Boolean);
      const response = await apiPost<BenchmarkResponse>("/benchmark", {
        suite_file: suiteFile,
        models,
        runs: runs ? Number(runs) : undefined,
      });
      setResult(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "benchmark failed");
    } finally {
      setLoading(false);
    }
  };

  const sortedRows = useMemo(() => {
    if (!result) return [];
    const rows = [...result.models];
    rows.sort((a, b) => {
      let cmp = 0;
      if (sortKey === "model") cmp = a.model.localeCompare(b.model);
      else if (sortKey === "pass_rate") cmp = a.pass_rate - b.pass_rate;
      else cmp = a.avg_latency_ms - b.avg_latency_ms;
      return sortDesc ? -cmp : cmp;
    });
    return rows;
  }, [result, sortKey, sortDesc]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDesc((d) => !d);
    else {
      setSortKey(key);
      setSortDesc(true);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-zinc-100">Benchmark</h1>
        <p className="text-zinc-500 mt-1">Compare the same suite across multiple models.</p>
      </div>

      <div className="bg-card border border-border rounded-xl p-4 space-y-3">
        <input
          value={suiteFile}
          onChange={(e) => setSuiteFile(e.target.value)}
          className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm font-mono"
          placeholder="tests/examples/booking.yaml"
        />
        <input
          value={modelsInput}
          onChange={(e) => setModelsInput(e.target.value)}
          className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm font-mono"
          placeholder="llama-3.3-70b-versatile,claude-haiku-4-5,gpt-4o-mini"
        />
        <div className="flex items-center gap-3">
          <input
            value={runs}
            onChange={(e) => setRuns(e.target.value)}
            className="w-32 bg-bg border border-border rounded-lg px-3 py-2 text-sm font-mono"
            placeholder="runs (opt.)"
          />
          <button
            onClick={handleBenchmark}
            disabled={loading}
            className="bg-accent hover:bg-accent/90 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
          >
            {loading ? "Benchmarking..." : "Run benchmark"}
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-failure/10 border border-failure/30 text-failure text-sm rounded-lg px-4 py-3">
          {error}
        </div>
      )}

      {result && (
        <>
          <div className="bg-card border border-border rounded-xl p-4">
            <h2 className="text-sm font-medium text-zinc-400 mb-3">Pass rate by model</h2>
            <BarChart data={sortedRows.map((r) => ({ label: r.model, value: r.pass_rate }))} />
          </div>

          <div className="bg-card border border-border rounded-xl overflow-hidden">
            <table className="w-full text-sm font-mono">
              <thead>
                <tr className="border-b border-border text-zinc-500 text-left">
                  {(
                    [
                      ["model", "Model"],
                      ["pass_rate", "Pass Rate"],
                      ["avg_latency_ms", "Avg Latency"],
                    ] as [SortKey, string][]
                  ).map(([key, label]) => (
                    <th
                      key={key}
                      onClick={() => toggleSort(key)}
                      className="px-4 py-2 font-normal cursor-pointer hover:text-zinc-200 select-none"
                    >
                      {label} {sortKey === key ? (sortDesc ? "▾" : "▴") : ""}
                    </th>
                  ))}
                  <th className="px-4 py-2 font-normal">Est. Cost / 100 Runs</th>
                  <th className="px-4 py-2 font-normal">Arg Accuracy</th>
                </tr>
              </thead>
              <tbody>
                {sortedRows.map((row) => (
                  <tr key={row.model} className="border-b border-border last:border-0 hover:bg-white/5">
                    <td className="px-4 py-2 text-zinc-200">{row.model}</td>
                    <td className="px-4 py-2 text-zinc-400">{(row.pass_rate * 100).toFixed(1)}%</td>
                    <td className="px-4 py-2 text-zinc-400">{row.avg_latency_ms.toFixed(0)}ms</td>
                    <td className="px-4 py-2 text-zinc-400">${estimatedCostPer100Runs(row.model).toFixed(2)}</td>
                    <td className="px-4 py-2 text-zinc-400">{(argAccuracy(row) * 100).toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
