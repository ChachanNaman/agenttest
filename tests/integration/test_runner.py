"""Integration tests for core/runner.py using a fake adapter (no real network calls)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.adapters.base import AdapterResponse, TokenUsage, ToolCall  # noqa: E402
from core.parser import CallAssertion, TestCase, TestSuite, ToolDef  # noqa: E402
from core import runner  # noqa: E402


class FakeAdapter:
    """Deterministic stand-in for a real LLM adapter, cycling through scripted responses."""

    def __init__(self, responses: list[AdapterResponse]) -> None:
        self._responses = responses
        self.call_count = 0

    async def call(self, system: str, messages: list, tools: list, model: str) -> AdapterResponse:
        response = self._responses[self.call_count % len(self._responses)]
        self.call_count += 1
        return response


def _make_suite(test: TestCase) -> TestSuite:
    return TestSuite(
        version="1.0",
        suite="Fake Suite",
        system_prompt="system",
        model="llama-3.3-70b-versatile",
        tools=[ToolDef(name="search_flights")],
        tests=[test],
    )


class RunTestTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_iterations_pass_when_adapter_always_matches(self) -> None:
        test = TestCase(
            name="always passes",
            message="book a flight",
            runs=5,
            pass_threshold=0.8,
            assert_calls=[CallAssertion(function="search_flights", args={})],
        )
        suite = _make_suite(test)
        fake_response = AdapterResponse(
            tool_calls=[ToolCall(name="search_flights", arguments={"city": "Paris"})],
            usage=TokenUsage(10, 5),
            latency_ms=100.0,
        )
        fake_adapter = FakeAdapter([fake_response])

        with patch.object(runner, "get_adapter", return_value=fake_adapter):
            result = await runner.run_test(test, suite)

        self.assertEqual(result.passes, 5)
        self.assertEqual(result.total, 5)
        self.assertTrue(result.meets_threshold)

    async def test_all_iterations_fail_when_adapter_never_matches(self) -> None:
        test = TestCase(
            name="always fails",
            message="book a flight",
            runs=5,
            pass_threshold=0.8,
            assert_calls=[CallAssertion(function="search_flights", args={})],
        )
        suite = _make_suite(test)
        fake_response = AdapterResponse(tool_calls=[], usage=TokenUsage(10, 5), latency_ms=100.0)
        fake_adapter = FakeAdapter([fake_response])

        with patch.object(runner, "get_adapter", return_value=fake_adapter):
            result = await runner.run_test(test, suite)

        self.assertEqual(result.passes, 0)
        self.assertFalse(result.meets_threshold)

    async def test_mixed_results_compute_correct_pass_rate(self) -> None:
        test = TestCase(
            name="mixed",
            message="book a flight",
            runs=4,
            pass_threshold=0.4,
            assert_calls=[CallAssertion(function="search_flights", args={})],
        )
        suite = _make_suite(test)
        passing = AdapterResponse(
            tool_calls=[ToolCall(name="search_flights", arguments={})], usage=TokenUsage(), latency_ms=50.0
        )
        failing = AdapterResponse(tool_calls=[], usage=TokenUsage(), latency_ms=50.0)
        fake_adapter = FakeAdapter([passing, failing])

        with patch.object(runner, "get_adapter", return_value=fake_adapter):
            result = await runner.run_test(test, suite)

        self.assertEqual(result.passes, 2)
        self.assertEqual(result.total, 4)

    async def test_progress_callback_fires_for_each_iteration(self) -> None:
        test = TestCase(
            name="progress test",
            message="book a flight",
            runs=3,
            pass_threshold=0.5,
            assert_calls=[CallAssertion(function="search_flights", args={})],
        )
        suite = _make_suite(test)
        fake_response = AdapterResponse(
            tool_calls=[ToolCall(name="search_flights", arguments={})], usage=TokenUsage(), latency_ms=10.0
        )
        fake_adapter = FakeAdapter([fake_response])

        events: list[dict[str, Any]] = []

        async def on_progress(event: dict[str, Any]) -> None:
            events.append(event)

        with patch.object(runner, "get_adapter", return_value=fake_adapter):
            await runner.run_test(test, suite, on_progress=on_progress)

        iteration_events = [e for e in events if e["type"] == "iteration_complete"]
        self.assertEqual(len(iteration_events), 3)
        self.assertEqual(events[0]["type"], "test_started")
        self.assertEqual(events[-1]["type"], "test_complete")


class RunSuiteTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_suite_runs_all_tests_sequentially(self) -> None:
        test1 = TestCase(name="t1", message="hi", runs=2, pass_threshold=0.5)
        test2 = TestCase(name="t2", message="hi", runs=2, pass_threshold=0.5)
        suite = TestSuite(
            version="1.0", suite="Multi", system_prompt="sys", model="llama-3.3-70b-versatile",
            tools=[], tests=[test1, test2],
        )
        fake_response = AdapterResponse(tool_calls=[], usage=TokenUsage(), latency_ms=10.0)
        fake_adapter = FakeAdapter([fake_response])

        with patch.object(runner, "get_adapter", return_value=fake_adapter):
            results = await runner.run_suite(suite)

        self.assertEqual(len(results), 2)
        self.assertEqual({r.test_name for r in results}, {"t1", "t2"})


if __name__ == "__main__":
    unittest.main()
