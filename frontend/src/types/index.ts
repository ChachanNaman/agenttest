export interface TestFailure {
  iteration: number;
  reasons: string[];
}

export interface TestResultSummary {
  test_name: string;
  passes: number;
  total: number;
  pass_rate: number;
  meets_threshold: boolean;
  verdict: string;
  ci_lower: number;
  ci_upper: number;
  avg_latency_ms: number;
  failures: TestFailure[];
}

export interface RunResponse {
  run_id: number | null;
  suite: string;
  results: TestResultSummary[];
}

export interface RunSummary {
  id: number;
  suite_name: string;
  test_name: string;
  model: string;
  started_at: string;
  completed_at: string | null;
  total_iterations: number;
  passes: number;
  pass_rate: number;
  threshold: number;
  meets_threshold: number;
  avg_latency_ms: number | null;
  ci_lower: number | null;
  ci_upper: number | null;
  flakiness_score: number | null;
}

export interface IterationRecord {
  id: number;
  run_id: number;
  iteration_number: number;
  passed: number;
  actual_calls: string;
  failure_reasons: string;
  latency_ms: number | null;
  token_count: number | null;
}

export interface RunDetail extends RunSummary {
  iterations: IterationRecord[];
}

export interface HistoryPoint {
  id: number;
  suite_name: string;
  test_name: string;
  started_at: string;
  pass_rate: number;
  threshold: number;
  avg_latency_ms: number | null;
  meets_threshold: number;
  flakiness_score: number | null;
}

export interface CompareRow {
  test_name: string;
  baseline_pass_rate: number;
  candidate_pass_rate: number;
  delta: number;
  p_value: number;
  is_regression: boolean;
  verdict: string;
}

export interface CompareResponse {
  suite: string;
  baseline_label: string;
  candidate_label: string;
  has_regression: boolean;
  results: CompareRow[];
}

export interface BenchmarkModelRow {
  model: string;
  pass_rate: number;
  avg_latency_ms: number;
  tests: { test_name: string; pass_rate: number; meets_threshold: boolean }[];
}

export interface BenchmarkResponse {
  suite: string;
  models: BenchmarkModelRow[];
}

export interface FlakinessRow {
  test_name: string;
  flakiness_score: number;
  current_pass_rate: number;
  pass_rate_variance: number;
  sample_size: number;
}

export type WebSocketEventType =
  | "run_started"
  | "test_started"
  | "iteration_complete"
  | "test_complete"
  | "run_complete"
  | "error";

export interface WsRunStarted {
  type: "run_started";
  suite: string;
  total_tests: number;
}

export interface WsTestStarted {
  type: "test_started";
  test_name: string;
  runs: number;
}

export interface WsIterationComplete {
  type: "iteration_complete";
  test_name: string;
  iteration: number;
  passed: boolean;
  current_pass_rate: number;
}

export interface WsTestComplete {
  type: "test_complete";
  test_name: string;
  pass_rate: number;
  meets_threshold: boolean;
  verdict: string;
}

export interface WsRunComplete {
  type: "run_complete";
  passed: number;
  failed: number;
  total: number;
}

export interface WsError {
  type: "error";
  message: string;
}

export type WsEvent =
  | WsRunStarted
  | WsTestStarted
  | WsIterationComplete
  | WsTestComplete
  | WsRunComplete
  | WsError;

export type ArgDiffStatus = "match" | "mismatch" | "missing" | "extra";
export type CallDiffStatus = "match" | "arg_mismatch" | "missing" | "extra";

export interface ArgDiff {
  key: string;
  expected_value: unknown;
  actual_value: unknown;
  status: ArgDiffStatus;
}

export interface CallDiff {
  function: string;
  status: CallDiffStatus;
  arg_diffs: ArgDiff[];
}

export interface LiveTestState {
  test_name: string;
  runs: number;
  completedIterations: number;
  currentPassRate: number;
  status: "pending" | "running" | "complete";
  finalVerdict?: string;
  finalPassRate?: number;
  meetsThreshold?: boolean;
  iterationOutcomes: boolean[];
}
