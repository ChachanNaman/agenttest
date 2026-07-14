import { useState } from "react";
import { DiffViewer } from "../components/DiffViewer";
import { apiPost } from "../hooks/useApi";
import type { CallDiff, CompareResponse, CompareRow } from "../types";

interface VariantForm {
  label: string;
  systemPrompt: string;
  model: string;
}
//
const EMPTY_BASELINE: VariantForm = { label: "baseline", systemPrompt: "", model: "" };
const EMPTY_CANDIDATE: VariantForm = { label: "candidate", systemPrompt: "", model: "" };
//
function VariantPanel({
  title,
  value,
  onChange,
}: {
  title: string;
  value: VariantForm;
  onChange: (v: VariantForm) => void;
}) {
  return (
    <div className="bg-card border border-border rounded-xl p-4 space-y-3">
      <h3 className="text-sm font-medium text-zinc-300">{title}</h3>
      <div>
        <label className="text-xs text-zinc-500">Label</label>
        <input
          value={value.label}
          onChange={(e) => onChange({ ...value, label: e.target.value })}
          className="w-full mt-1 bg-bg border border-border rounded-lg px-3 py-1.5 text-sm font-mono"
        />
      </div>
      <div>
        <label className="text-xs text-zinc-500">Model override (optional)</label>
        <input
          value={value.model}
          onChange={(e) => onChange({ ...value, model: e.target.value })}
          placeholder="leave blank to use suite default"
          className="w-full mt-1 bg-bg border border-border rounded-lg px-3 py-1.5 text-sm font-mono"
        />
      </div>
      <div>
        <label className="text-xs text-zinc-500">System prompt override (optional)</label>
        <textarea
          value={value.systemPrompt}
          onChange={(e) => onChange({ ...value, systemPrompt: e.target.value })}
          placeholder="leave blank to use suite default"
          rows={4}
          className="w-full mt-1 bg-bg border border-border rounded-lg px-3 py-1.5 text-sm font-mono resize-none"
        />
      </div>
    </div>
  );
}

function buildStatDiff(row: CompareRow): CallDiff[] {
  return [
    {
      function: row.test_name,
      status: row.is_regression ? "arg_mismatch" : "match",
      arg_diffs: [
        { key: "baseline_pass_rate", expected_value: row.baseline_pass_rate, actual_value: row.candidate_pass_rate, status: row.is_regression ? "mismatch" : "match" },
        { key: "p_value", expected_value: 0.05, actual_value: row.p_value, status: row.p_value < 0.05 ? "mismatch" : "match" },
      ],
    },
  ];
}

export function Compare() {
  const [suiteFile, setSuiteFile] = useState("tests/examples/booking.yaml");
  const [runs, setRuns] = useState("");
  const [baseline, setBaseline] = useState<VariantForm>(EMPTY_BASELINE);
  const [candidate, setCandidate] = useState<VariantForm>(EMPTY_CANDIDATE);
  const [result, setResult] = useState<CompareResponse | null>(null);
  const [selectedRow, setSelectedRow] = useState<CompareRow | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCompare = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const response = await apiPost<CompareResponse>("/compare", {
        suite_file: suiteFile,
        runs: runs ? Number(runs) : undefined,
        baseline: {
          label: baseline.label,
          system_prompt: baseline.systemPrompt || undefined,
          model: baseline.model || undefined,
        },
        candidate: {
          label: candidate.label,
          system_prompt: candidate.systemPrompt || undefined,
          model: candidate.model || undefined,
        },
      });
      setResult(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "comparison failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-zinc-100">Compare</h1>
        <p className="text-zinc-500 mt-1">
          Run a suite under two configurations and check for statistically significant regressions.
        </p>
      </div>

      <div className="bg-card border border-border rounded-xl p-4 flex items-center gap-3">
        <input
          value={suiteFile}
          onChange={(e) => setSuiteFile(e.target.value)}
          className="flex-1 bg-bg border border-border rounded-lg px-3 py-2 text-sm font-mono"
          placeholder="tests/examples/booking.yaml"
        />
        <input
          value={runs}
          onChange={(e) => setRuns(e.target.value)}
          className="w-28 bg-bg border border-border rounded-lg px-3 py-2 text-sm font-mono"
          placeholder="runs (opt.)"
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <VariantPanel title="Baseline" value={baseline} onChange={setBaseline} />
        <VariantPanel title="Candidate" value={candidate} onChange={setCandidate} />
      </div>

      <button
        onClick={handleCompare}
        disabled={loading}
        className="bg-accent hover:bg-accent/90 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
      >
        {loading ? "Running comparison..." : "Run comparison"}
      </button>

      {error && (
        <div className="bg-failure/10 border border-failure/30 text-failure text-sm rounded-lg px-4 py-3">
          {error}
        </div>
      )}

      {result && (
        <div className="bg-card border border-border rounded-xl overflow-hidden">
          <table className="w-full text-sm font-mono">
            <thead>
              <tr className="border-b border-border text-zinc-500 text-left">
                <th className="px-4 py-2 font-normal">Test Name</th>
                <th className="px-4 py-2 font-normal">Baseline</th>
                <th className="px-4 py-2 font-normal">Candidate</th>
                <th className="px-4 py-2 font-normal">Change</th>
                <th className="px-4 py-2 font-normal">P-Value</th>
                <th className="px-4 py-2 font-normal">Status</th>
              </tr>
            </thead>
            <tbody>
              {result.results.map((row) => (
                <tr
                  key={row.test_name}
                  onClick={() => setSelectedRow(row)}
                  className={`border-b border-border last:border-0 cursor-pointer hover:bg-white/5 ${
                    row.is_regression ? "bg-failure/5" : ""
                  }`}
                >
                  <td className="px-4 py-2 text-zinc-200">{row.test_name}</td>
                  <td className="px-4 py-2 text-zinc-400">{(row.baseline_pass_rate * 100).toFixed(1)}%</td>
                  <td className="px-4 py-2 text-zinc-400">{(row.candidate_pass_rate * 100).toFixed(1)}%</td>
                  <td className={row.delta < 0 ? "px-4 py-2 text-failure" : "px-4 py-2 text-success"}>
                    {row.delta >= 0 ? "+" : ""}
                    {(row.delta * 100).toFixed(1)}%
                  </td>
                  <td className="px-4 py-2 text-zinc-400">{row.p_value.toFixed(3)}</td>
                  <td className={row.is_regression ? "px-4 py-2 text-failure" : "px-4 py-2 text-success"}>
                    {row.is_regression ? "✗ REGRESSION" : "✓ No change"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selectedRow && (
        <div>
          <h2 className="text-sm font-medium text-zinc-400 mb-2">
            Detail: {selectedRow.test_name}
            <span className="ml-2 text-zinc-600 font-normal">{selectedRow.verdict}</span>
          </h2>
          <DiffViewer callDiffs={buildStatDiff(selectedRow)} />
        </div>
      )}
    </div>
  );
}
