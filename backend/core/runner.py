"""Async parallel test runner: executes a TestSuite's tests against a live LLM adapter."""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

from .adapters import get_adapter
from .adapters.base import AdapterAuthError, AdapterError, AdapterRateLimitError, AdapterResponse, ToolCall
from .assertions import RunResult, evaluate_run
from .parser import ConversationTurn, TestCase, TestSuite
from .stats import PassRateResult, compute_pass_rate

MAX_CONCURRENT_CALLS = 5
MAX_RETRIES = 3
BASE_RETRY_DELAY_SECONDS = 1.0

# Retrying a per-minute token quota on the same 1s/2s/4s schedule as a transient
# network error is pointless — the quota won't have reset. Rate limits get their
# own longer, jittered schedule (and honor a provider's Retry-After hint when given).
RATE_LIMIT_MAX_RETRIES = 5
RATE_LIMIT_MAX_DELAY_SECONDS = 15.0
RATE_LIMIT_JITTER_SECONDS = 0.5

ProgressCallback = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass
class TestResult:
    """Aggregated outcome of running one TestCase for `runs` iterations."""

    test_name: str
    total: int
    passes: int
    pass_rate: float
    ci_lower: float
    ci_upper: float
    meets_threshold: bool
    threshold: float
    verdict: str
    avg_latency_ms: float
    run_results: list[RunResult] = field(default_factory=list)

    @staticmethod
    def from_run_results(test: TestCase, run_results: list[RunResult]) -> "TestResult":
        passes = sum(1 for r in run_results if r.passed)
        summary: PassRateResult = compute_pass_rate(passes, len(run_results), test.pass_threshold)
        latencies = [r.latency_ms for r in run_results if r.latency_ms]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        return TestResult(
            test_name=test.name,
            total=summary.total,
            passes=summary.passes,
            pass_rate=summary.pass_rate,
            ci_lower=summary.ci_lower,
            ci_upper=summary.ci_upper,
            meets_threshold=summary.meets_threshold,
            threshold=summary.threshold,
            verdict=summary.verdict,
            avg_latency_ms=avg_latency,
            run_results=run_results,
        )


async def _emit(callback: Optional[ProgressCallback], event: dict[str, Any]) -> None:
    if callback is not None:
        await callback(event)


async def _call_with_retries(
    adapter: Any, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]], model: str
) -> AdapterResponse:
    """Call the adapter with exponential backoff. Rate limits get a longer, jittered
    schedule (see RATE_LIMIT_*) since retrying quickly against a per-minute quota just
    burns the retry budget without the quota ever having a chance to reset."""
    rate_limit_attempt = 0
    attempt = 0
    while True:
        try:
            return await adapter.call(system, messages, tools, model)
        except AdapterAuthError:
            raise  # retrying won't fix a missing/invalid API key
        except AdapterRateLimitError as exc:
            rate_limit_attempt += 1
            if rate_limit_attempt >= RATE_LIMIT_MAX_RETRIES:
                raise
            delay = exc.retry_after_seconds or BASE_RETRY_DELAY_SECONDS * (2**rate_limit_attempt)
            delay = min(delay, RATE_LIMIT_MAX_DELAY_SECONDS) + random.uniform(0, RATE_LIMIT_JITTER_SECONDS)
            await asyncio.sleep(delay)
        except AdapterError:
            attempt += 1
            if attempt >= MAX_RETRIES:
                raise
            await asyncio.sleep(BASE_RETRY_DELAY_SECONDS * (2 ** (attempt - 1)))


async def _run_single_turn_iteration(
    test: TestCase, suite: TestSuite, adapter: Any, tool_schemas: list[dict[str, Any]]
) -> RunResult:
    messages = [{"role": "user", "content": test.message}]
    try:
        response = await _call_with_retries(adapter, suite.system_prompt, messages, tool_schemas, suite.model)
    except AdapterAuthError as exc:
        return RunResult(passed=False, actual_calls=[], failure_reasons=[f"adapter auth failed: {exc}"])
    except AdapterRateLimitError as exc:
        return RunResult(
            passed=False,
            actual_calls=[],
            failure_reasons=[f"adapter call failed after {RATE_LIMIT_MAX_RETRIES} rate-limit retries: {exc}"],
        )
    except AdapterError as exc:
        return RunResult(
            passed=False,
            actual_calls=[],
            failure_reasons=[f"adapter call failed after {MAX_RETRIES} attempts: {exc}"],
        )
    return evaluate_run(
        test, response.tool_calls, latency_ms=response.latency_ms, token_count=response.usage.total_tokens
    )


async def _run_conversation_iteration(
    test: TestCase, suite: TestSuite, adapter: Any, tool_schemas: list[dict[str, Any]]
) -> RunResult:
    """Run a multi-turn conversation sequentially, asserting tool calls at each turn."""
    messages: list[dict[str, Any]] = []
    all_calls: list[ToolCall] = []
    total_latency = 0.0
    total_tokens = 0
    failure_reasons: list[str] = []

    for turn in test.conversation:
        messages.append({"role": turn.role, "content": turn.message})
        try:
            response = await _call_with_retries(
                adapter, suite.system_prompt, messages, tool_schemas, suite.model
            )
        except AdapterError as exc:
            failure_reasons.append(f"turn '{turn.message[:40]}...' failed: {exc}")
            break

        total_latency += response.latency_ms
        total_tokens += response.usage.total_tokens
        all_calls.extend(response.tool_calls)
        messages.append({"role": "assistant", "content": response.text or ""})

        failure_reasons.extend(_check_turn_assertions(turn, response.tool_calls))

    passed = not failure_reasons
    return RunResult(
        passed=passed,
        actual_calls=all_calls,
        failure_reasons=failure_reasons,
        latency_ms=total_latency,
        token_count=total_tokens,
    )


def _check_turn_assertions(turn: ConversationTurn, actual_calls: list[ToolCall]) -> list[str]:
    called_names = {c.name for c in actual_calls}
    reasons = []
    for expected_fn in turn.assert_calls:
        if expected_fn not in called_names:
            reasons.append(f"turn '{turn.message[:40]}...': expected call to '{expected_fn}' but it was not made")
    return reasons


async def run_test(
    test: TestCase, suite: TestSuite, on_progress: Optional[ProgressCallback] = None
) -> TestResult:
    """Run one test `test.runs` times in parallel (bounded concurrency) and aggregate results."""
    adapter = get_adapter(suite.model)
    tool_schemas = [t.to_openai_schema() for t in suite.tools]
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_CALLS)

    await _emit(on_progress, {"type": "test_started", "test_name": test.name, "runs": test.runs})

    completed_count = 0
    passed_count = 0
    lock = asyncio.Lock()

    async def run_one(iteration: int) -> RunResult:
        nonlocal completed_count, passed_count
        async with semaphore:
            if test.is_multi_turn:
                result = await _run_conversation_iteration(test, suite, adapter, tool_schemas)
            else:
                result = await _run_single_turn_iteration(test, suite, adapter, tool_schemas)

        async with lock:
            completed_count += 1
            if result.passed:
                passed_count += 1
            await _emit(
                on_progress,
                {
                    "type": "iteration_complete",
                    "test_name": test.name,
                    "iteration": completed_count,
                    "passed": result.passed,
                    "current_pass_rate": passed_count / completed_count,
                },
            )
        return result

    tasks = [run_one(i) for i in range(test.runs)]
    gathered = await asyncio.gather(*tasks, return_exceptions=True)

    run_results: list[RunResult] = []
    for outcome in gathered:
        if isinstance(outcome, Exception):
            run_results.append(RunResult(passed=False, actual_calls=[], failure_reasons=[str(outcome)]))
        else:
            run_results.append(outcome)

    result = TestResult.from_run_results(test, run_results)
    await _emit(
        on_progress,
        {
            "type": "test_complete",
            "test_name": test.name,
            "pass_rate": result.pass_rate,
            "meets_threshold": result.meets_threshold,
            "verdict": result.verdict,
        },
    )
    return result


async def run_suite(suite: TestSuite, on_progress: Optional[ProgressCallback] = None) -> list[TestResult]:
    """Run every test in a suite sequentially (each test's iterations run in parallel)."""
    await _emit(on_progress, {"type": "run_started", "suite": suite.suite, "total_tests": len(suite.tests)})

    results: list[TestResult] = []
    for test in suite.tests:
        results.append(await run_test(test, suite, on_progress))

    passed = sum(1 for r in results if r.meets_threshold)
    await _emit(
        on_progress,
        {
            "type": "run_complete",
            "passed": passed,
            "failed": len(results) - passed,
            "total": len(results),
        },
    )
    return results
