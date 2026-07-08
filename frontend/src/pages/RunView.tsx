import { useCallback, useState } from "react";
import { TestCard } from "../components/TestCard";
import { LiveFeed } from "../components/LiveFeed";
import { useRunSocket } from "../hooks/useWebSocket";
import type { LiveTestState, WsEvent } from "../types";

const DEFAULT_SUITE_FILE = "tests/examples/booking.yaml";

interface RunState {
  suiteName: string | null;
  totalTests: number;
  order: string[];
  tests: Record<string, LiveTestState>;
  finished: boolean;
  summary: { passed: number; failed: number; total: number } | null;
}

const INITIAL_RUN_STATE: RunState = {
  suiteName: null,
  totalTests: 0,
  order: [],
  tests: {},
  finished: false,
  summary: null,
};

export function RunView() {
  const [suiteFile, setSuiteFile] = useState(DEFAULT_SUITE_FILE);
  const [events, setEvents] = useState<WsEvent[]>([]);
  const [runState, setRunState] = useState<RunState>(INITIAL_RUN_STATE);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleEvent = useCallback((event: WsEvent) => {
    setEvents((prev) => [...prev, event]);

    setRunState((prev) => {
      switch (event.type) {
        case "run_started":
          return {
            suiteName: event.suite,
            totalTests: event.total_tests,
            order: [],
            tests: {},
            finished: false,
            summary: null,
          };
        case "test_started":
          return {
            ...prev,
            order: [...prev.order, event.test_name],
            tests: {
              ...prev.tests,
              [event.test_name]: {
                test_name: event.test_name,
                runs: event.runs,
                completedIterations: 0,
                currentPassRate: 0,
                status: "running",
                iterationOutcomes: [],
              },
            },
          };
        case "iteration_complete": {
          const existing = prev.tests[event.test_name];
          if (!existing) return prev;
          return {
            ...prev,
            tests: {
              ...prev.tests,
              [event.test_name]: {
                ...existing,
                completedIterations: event.iteration,
                currentPassRate: event.current_pass_rate,
                iterationOutcomes: [...existing.iterationOutcomes, event.passed],
              },
            },
          };
        }
        case "test_complete": {
          const existing = prev.tests[event.test_name];
          if (!existing) return prev;
          return {
            ...prev,
            tests: {
              ...prev.tests,
              [event.test_name]: {
                ...existing,
                status: "complete",
                finalVerdict: event.verdict,
                finalPassRate: event.pass_rate,
                meetsThreshold: event.meets_threshold,
              },
            },
          };
        }
        case "run_complete":
          return {
            ...prev,
            finished: true,
            summary: { passed: event.passed, failed: event.failed, total: event.total },
          };
        case "error":
          setErrorMessage(event.message);
          return prev;
        default:
          return prev;
      }
    });
  }, []);

  const { status, start } = useRunSocket({ onEvent: handleEvent });

  const handleRun = () => {
    setErrorMessage(null);
    setEvents([]);
    setRunState(INITIAL_RUN_STATE);
    start(suiteFile);
  };

  const isRunning = status === "connecting" || status === "open";
  const completedTests = Object.values(runState.tests).filter((t) => t.status === "complete").length;
  const overallProgress = runState.totalTests > 0 ? completedTests / runState.totalTests : 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-zinc-100">Run a test suite</h1>
        <p className="text-zinc-500 mt-1">Trigger tests and watch results stream in live.</p>
      </div>

      <div className="bg-card border border-border rounded-xl p-4 flex items-center gap-3">
        <input
          type="text"
          value={suiteFile}
          onChange={(e) => setSuiteFile(e.target.value)}
          placeholder="tests/examples/booking.yaml"
          className="flex-1 bg-bg border border-border rounded-lg px-3 py-2 text-sm font-mono text-zinc-100 focus:outline-none focus:ring-1 focus:ring-accent"
        />
        <button
          onClick={handleRun}
          disabled={isRunning || !suiteFile}
          className="bg-accent hover:bg-accent/90 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
        >
          {isRunning ? "Running..." : "Run suite"}
        </button>
      </div>

      {errorMessage && (
        <div className="bg-failure/10 border border-failure/30 text-failure text-sm rounded-lg px-4 py-3">
          {errorMessage}
        </div>
      )}

      {runState.totalTests > 0 && (
        <div>
          <div className="flex items-center justify-between text-sm text-zinc-400 mb-1.5">
            <span>{runState.suiteName}</span>
            <span className="font-mono">
              {completedTests}/{runState.totalTests} tests
            </span>
          </div>
          <div className="h-2 bg-border rounded-full overflow-hidden">
            <div
              className="h-full bg-accent transition-all duration-300"
              style={{ width: `${overallProgress * 100}%` }}
            />
          </div>
          {runState.summary && (
            <p className="text-sm mt-2 text-zinc-400">
              {runState.summary.passed}/{runState.summary.total} tests passed
            </p>
          )}
        </div>
      )}

      <div className="grid gap-3">
        {runState.order.map((testName) => {
          const test = runState.tests[testName];
          return test ? <TestCard key={testName} state={test} /> : null;
        })}
      </div>

      <div>
        <h2 className="text-sm font-medium text-zinc-400 mb-2">Live feed</h2>
        <LiveFeed events={events} />
      </div>
    </div>
  );
}
