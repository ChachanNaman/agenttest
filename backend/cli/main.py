"""Agenttest CLI. Argument parsing is done by hand from sys.argv (no argparse/click/typer)."""

from __future__ import annotations

import asyncio
import dataclasses
import os
import sys
from pathlib import Path

CLI_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CLI_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core import storage  # noqa: E402
from core.parser import SuiteParseError, TestSuite, parse_suite_file  # noqa: E402
from core.runner import TestResult, run_suite  # noqa: E402
from core.stats import detect_regression  # noqa: E402

VERSION = "1.0.0"

CHECK = "✓"
CROSS = "✗"
TRIANGLE = "▸"

SAMPLE_SUITE = """\
version: "1.0"
suite: "My First Agent"
system_prompt: "You are a helpful assistant. Use tools when appropriate."
model: "llama-3.3-70b-versatile"

tools:
  - name: get_weather
    description: "Get the current weather for a city"
    parameters:
      city: {type: string, description: "City name"}
    required: [city]

tests:
  - name: "asks for weather"
    message: "What's the weather like in Paris?"
    runs: 10
    pass_threshold: 0.8

    assert_calls:
      - function: get_weather
        args:
          city: {equals: "Paris"}
"""


def _load_dotenv() -> None:
    path = BACKEND_DIR.parent / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _parse_flags(argv: list[str]) -> dict[str, str]:
    """Parse `--key value` pairs from a flat argv list into a dict."""
    flags: dict[str, str] = {}
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg.startswith("--"):
            key = arg[2:]
            if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                flags[key] = argv[i + 1]
                i += 2
            else:
                flags[key] = "true"
                i += 1
        else:
            i += 1
    return flags


def _resolve_prompt(value: str) -> str:
    """A --baseline/--candidate value may be a path to a prompt file, or literal prompt text."""
    path = Path(value)
    if path.is_file():
        return path.read_text().strip()
    return value


def cmd_run(argv: list[str]) -> int:
    if not argv:
        print("usage: agenttest run <file>")
        return 1
    file_path = argv[0]

    print(f"\U0001f9ea Agenttest v{VERSION}")

    try:
        suite = parse_suite_file(file_path)
    except SuiteParseError as exc:
        print(f"{CROSS} {exc}")
        return 1

    print(f"Running suite: {suite.suite}")
    print(f"Model: {suite.model}\n")

    storage.init_db()
    storage.register_suite(suite.suite, file_path)

    results: list[TestResult] = asyncio.run(run_suite(suite))

    all_passed = True
    for result in results:
        print(f"  {TRIANGLE} {result.test_name} ({result.total} runs)...")
        symbol = CHECK if result.meets_threshold else CROSS
        status = "PASS" if result.meets_threshold else "FAIL"
        pct = result.pass_rate * 100
        lo, hi = result.ci_lower * 100, result.ci_upper * 100
        print(
            f"    {symbol} {status} — {pct:.1f}% (CI: {lo:.0f}–{hi:.0f}%) | "
            f"{result.avg_latency_ms:,.0f}ms avg"
        )
        if not result.meets_threshold:
            all_passed = False
            failing = [r for r in result.run_results if not r.passed]
            if failing:
                reasons = failing[0].failure_reasons
                reason_text = reasons[0] if reasons else "assertions failed"
                print(f"      Reason: {reason_text} ({len(failing)}/{result.total} runs)")
        storage.save_test_result(suite.suite, suite.model, result)

    passed_count = sum(1 for r in results if r.meets_threshold)
    print("\n" + "─" * 34)
    print(f"Results: {passed_count}/{len(results)} tests passed")
    exit_code = 0 if all_passed else 1
    print(f"Exit code: {exit_code} ({'success' if exit_code == 0 else 'failure'})")
    return exit_code


def cmd_compare(argv: list[str]) -> int:
    flags = _parse_flags(argv)
    required = ["baseline", "candidate", "suite"]
    missing = [f for f in required if f not in flags]
    if missing:
        print(f"usage: agenttest compare --baseline <file_or_prompt> --candidate <file_or_prompt> "
              f"--suite <file> [--runs <n>]")
        print(f"missing required flags: {missing}")
        return 1

    try:
        suite = parse_suite_file(flags["suite"])
    except SuiteParseError as exc:
        print(f"{CROSS} {exc}")
        return 1

    runs_override = int(flags["runs"]) if "runs" in flags else None

    def build_variant(prompt_value: str) -> TestSuite:
        tests = suite.tests
        if runs_override is not None:
            tests = [dataclasses.replace(t, runs=runs_override) for t in tests]
        return dataclasses.replace(suite, system_prompt=_resolve_prompt(prompt_value), tests=tests)

    baseline_suite = build_variant(flags["baseline"])
    candidate_suite = build_variant(flags["candidate"])

    print(f"\U0001f9ea Agenttest v{VERSION} — Compare")
    print(f"Suite: {suite.suite}\n")

    baseline_results = {r.test_name: r for r in asyncio.run(run_suite(baseline_suite))}
    candidate_results = {r.test_name: r for r in asyncio.run(run_suite(candidate_suite))}

    header = f"{'Test Name':<28}{'Baseline':<12}{'Candidate':<12}{'Change':<10}{'P-Value':<10}Status"
    print(header)
    print("─" * len(header))

    has_regression = False
    for name, base in baseline_results.items():
        cand = candidate_results.get(name)
        if cand is None:
            continue
        reg = detect_regression(base.passes, base.total, cand.passes, cand.total)
        status = f"{CROSS} REGRESSION" if reg.is_regression else f"{CHECK} No change"
        if reg.is_regression:
            has_regression = True
        print(
            f"{name:<28}{reg.baseline_pass_rate * 100:<11.1f}%{reg.candidate_pass_rate * 100:<11.1f}%"
            f"{reg.delta * 100:<+9.1f}%{reg.p_value:<10.3f}{status}"
        )

    return 1 if has_regression else 0


def cmd_benchmark(argv: list[str]) -> int:
    flags = _parse_flags(argv)
    if "suite" not in flags or "models" not in flags:
        print("usage: agenttest benchmark --suite <file> --models <comma-separated> [--runs <n>]")
        return 1

    try:
        suite = parse_suite_file(flags["suite"])
    except SuiteParseError as exc:
        print(f"{CROSS} {exc}")
        return 1

    models = [m.strip() for m in flags["models"].split(",") if m.strip()]
    runs_override = int(flags["runs"]) if "runs" in flags else None

    print(f"\U0001f9ea Agenttest v{VERSION} — Benchmark")
    print(f"Suite: {suite.suite}\n")

    rows = []
    for model in models:
        tests = suite.tests
        if runs_override is not None:
            tests = [dataclasses.replace(t, runs=runs_override) for t in tests]
        model_suite = dataclasses.replace(suite, model=model, tests=tests)
        results = asyncio.run(run_suite(model_suite))
        total_passes = sum(r.passes for r in results)
        total_runs = sum(r.total for r in results)
        latencies = [r.avg_latency_ms for r in results if r.avg_latency_ms]
        rows.append(
            {
                "model": model,
                "pass_rate": total_passes / total_runs if total_runs else 0.0,
                "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0.0,
            }
        )

    rows.sort(key=lambda r: r["pass_rate"], reverse=True)
    header = f"{'Model':<32}{'Pass Rate':<14}Avg Latency"
    print(header)
    print("─" * len(header))
    for row in rows:
        print(f"{row['model']:<32}{row['pass_rate'] * 100:<13.1f}%{row['avg_latency_ms']:,.0f}ms")

    return 0


def cmd_serve(argv: list[str]) -> int:
    import uvicorn

    import main as app_module

    port = int(os.environ.get("PORT", 8000))
    print(f"\U0001f9ea Agenttest v{VERSION} — serving on http://localhost:{port}")
    uvicorn.run(app_module.app, host="0.0.0.0", port=port)
    return 0


def cmd_init(argv: list[str]) -> int:
    target = Path("agenttest.yaml")
    if target.exists():
        print(f"{CROSS} {target} already exists — not overwriting")
        return 1
    target.write_text(SAMPLE_SUITE)
    print(f"{CHECK} Created {target}")
    print("Edit it, then run: agenttest run agenttest.yaml")
    return 0


def cmd_report(argv: list[str]) -> int:
    if not argv:
        print("usage: agenttest report <run_id>")
        return 1
    try:
        run_id = int(argv[0])
    except ValueError:
        print(f"{CROSS} run_id must be an integer")
        return 1

    storage.init_db()
    run = storage.get_run(run_id)
    if run is None:
        print(f"{CROSS} run {run_id} not found")
        return 1

    print(f"Run #{run['id']} — {run['suite_name']} / {run['test_name']}")
    print(f"Model: {run['model']}")
    print(f"Started: {run['started_at']}  Completed: {run['completed_at']}")
    print(
        f"Passes: {run['passes']}/{run['total_iterations']} "
        f"({run['pass_rate'] * 100:.1f}%) threshold={run['threshold'] * 100:.0f}%"
    )
    print(f"95% CI: {run['ci_lower'] * 100:.0f}–{run['ci_upper'] * 100:.0f}%")
    if run.get("flakiness_score") is not None:
        print(f"Flakiness: {run['flakiness_score']:.2f}")
    print(f"\nIterations ({len(run['iterations'])}):")
    for it in run["iterations"]:
        symbol = CHECK if it["passed"] else CROSS
        print(f"  {symbol} #{it['iteration_number']}  {it['latency_ms']:.0f}ms")
        if not it["passed"]:
            import json

            for reason in json.loads(it["failure_reasons"]):
                print(f"      - {reason}")
    return 0


COMMANDS = {
    "run": cmd_run,
    "compare": cmd_compare,
    "benchmark": cmd_benchmark,
    "serve": cmd_serve,
    "init": cmd_init,
    "report": cmd_report,
}


def main() -> int:
    _load_dotenv()
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        print(f"Agenttest v{VERSION} — a testing framework for LLM agents\n")
        print("Usage: agenttest <command> [options]\n")
        print("Commands:")
        print("  run <file>                                        Run a test suite")
        print("  compare --baseline X --candidate Y --suite F       Regression comparison")
        print("  benchmark --suite F --models a,b,c                 Compare models")
        print("  serve                                              Start API + dashboard")
        print("  init                                               Create a sample suite")
        print("  report <run_id>                                    Show a detailed run report")
        return 0

    command, rest = argv[0], argv[1:]
    handler = COMMANDS.get(command)
    if handler is None:
        print(f"{CROSS} unknown command '{command}'. Run 'agenttest --help' for usage.")
        return 1
    return handler(rest)


if __name__ == "__main__":
    sys.exit(main())
