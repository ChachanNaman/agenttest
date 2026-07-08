"""Assertion engine: evaluates a test case's assertions against a set of actual tool calls."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .adapters.base import ToolCall
from .parser import ArgAssertion, CallAssertion, TestCase, compiled_regex, python_type_for


@dataclass
class AssertionResult:
    """The outcome of evaluating a single assertion."""

    passed: bool
    description: str
    reason: Optional[str] = None


@dataclass
class RunResult:
    """The outcome of evaluating all assertions for a single test iteration."""

    passed: bool
    actual_calls: list[ToolCall]
    assertion_results: list[AssertionResult] = field(default_factory=list)
    failure_reasons: list[str] = field(default_factory=list)
    latency_ms: float = 0.0
    token_count: int = 0


def _values_equal(expected: Any, actual: Any) -> bool:
    if isinstance(expected, str) and isinstance(actual, str):
        return expected.strip().lower() == actual.strip().lower()
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return float(expected) == float(actual)
    return expected == actual


def check_arg(arg_name: str, assertion: ArgAssertion, actual_args: dict[str, Any]) -> AssertionResult:
    """Evaluate a single argument assertion against the actual call arguments."""
    has_value = arg_name in actual_args and actual_args[arg_name] is not None
    actual_value = actual_args.get(arg_name)
    desc = f"arg '{arg_name}'"

    if assertion.not_null is True and not has_value:
        return AssertionResult(False, desc, f"expected '{arg_name}' to be non-null, got missing/null")

    if assertion.equals is not None:
        if not has_value:
            return AssertionResult(False, desc, f"expected '{arg_name}' == {assertion.equals!r}, but arg was missing")
        if not _values_equal(assertion.equals, actual_value):
            return AssertionResult(
                False, desc, f"expected '{arg_name}' == {assertion.equals!r}, got {actual_value!r}"
            )

    if assertion.type is not None:
        expected_pytype = python_type_for(assertion.type)
        if not has_value:
            return AssertionResult(False, desc, f"expected '{arg_name}' to be type {assertion.type}, but arg was missing")
        if isinstance(actual_value, bool) and expected_pytype is not bool:
            return AssertionResult(False, desc, f"expected '{arg_name}' to be type {assertion.type}, got bool")
        if not isinstance(actual_value, expected_pytype):
            return AssertionResult(
                False, desc, f"expected '{arg_name}' to be type {assertion.type}, got {type(actual_value).__name__}"
            )

    if assertion.contains is not None:
        if not has_value or not isinstance(actual_value, str) or assertion.contains not in actual_value:
            return AssertionResult(
                False, desc, f"expected '{arg_name}' to contain {assertion.contains!r}, got {actual_value!r}"
            )

    if assertion.matches is not None:
        pattern = compiled_regex(assertion.matches)
        if not has_value or not isinstance(actual_value, str) or not pattern.search(actual_value):
            return AssertionResult(
                False, desc, f"expected '{arg_name}' to match /{assertion.matches}/, got {actual_value!r}"
            )

    return AssertionResult(True, desc)


def _call_satisfies(call_assertion: CallAssertion, call: ToolCall) -> list[AssertionResult]:
    if call.name != call_assertion.function:
        return [AssertionResult(False, f"function '{call_assertion.function}'", "name mismatch")]
    return [check_arg(name, a, call.arguments) for name, a in call_assertion.args.items()]


def check_call(call_assertion: CallAssertion, actual_calls: list[ToolCall]) -> AssertionResult:
    """A call assertion passes if ANY actual call matches the function name and all arg checks."""
    candidates = [c for c in actual_calls if c.name == call_assertion.function]
    if not candidates:
        return AssertionResult(
            False,
            f"call '{call_assertion.function}'",
            f"expected '{call_assertion.function}' to be called, but it was never called",
        )

    best_failures: list[str] = []
    for call in candidates:
        arg_results = [check_arg(name, a, call.arguments) for name, a in call_assertion.args.items()]
        failures = [r.reason for r in arg_results if not r.passed and r.reason]
        if not failures:
            return AssertionResult(True, f"call '{call_assertion.function}'")
        if not best_failures or len(failures) < len(best_failures):
            best_failures = failures

    return AssertionResult(
        False,
        f"call '{call_assertion.function}'",
        f"'{call_assertion.function}' was called {len(candidates)}x but none matched args: "
        + "; ".join(best_failures),
    )


def check_no_calls(forbidden: list[str], actual_calls: list[ToolCall]) -> list[AssertionResult]:
    """Verify that none of the forbidden function names appear in actual_calls."""
    results = []
    called_names = {c.name for c in actual_calls}
    for fn in forbidden:
        if fn in called_names:
            results.append(
                AssertionResult(False, f"no call to '{fn}'", f"'{fn}' was called but was forbidden")
            )
        else:
            results.append(AssertionResult(True, f"no call to '{fn}'"))
    return results


def check_order(expected_order: list[str], actual_calls: list[ToolCall]) -> AssertionResult:
    """Verify expected_order appears as a (not necessarily contiguous) subsequence of actual_calls."""
    if not expected_order:
        return AssertionResult(True, "call order")

    actual_names = [c.name for c in actual_calls]
    cursor = 0
    for expected_name in expected_order:
        found = False
        while cursor < len(actual_names):
            if actual_names[cursor] == expected_name:
                found = True
                cursor += 1
                break
            cursor += 1
        if not found:
            return AssertionResult(
                False,
                "call order",
                f"expected order {expected_order}, but '{expected_name}' did not appear "
                f"in sequence after the prior expected calls (actual: {actual_names})",
            )
    return AssertionResult(True, "call order")


def check_after(call_assertion: CallAssertion, actual_calls: list[ToolCall]) -> AssertionResult:
    """If call_assertion.after is set, verify the target function appears before the first matching call."""
    if not call_assertion.after:
        return AssertionResult(True, f"'{call_assertion.function}' after constraint")

    names = [c.name for c in actual_calls]
    target_idx = next((i for i, n in enumerate(names) if n == call_assertion.function), None)
    after_idx = next((i for i, n in enumerate(names) if n == call_assertion.after), None)

    if target_idx is None:
        return AssertionResult(
            False,
            f"'{call_assertion.function}' after '{call_assertion.after}'",
            f"'{call_assertion.function}' was never called",
        )
    if after_idx is None:
        return AssertionResult(
            False,
            f"'{call_assertion.function}' after '{call_assertion.after}'",
            f"'{call_assertion.after}' was never called before '{call_assertion.function}'",
        )
    if after_idx >= target_idx:
        return AssertionResult(
            False,
            f"'{call_assertion.function}' after '{call_assertion.after}'",
            f"'{call_assertion.function}' (index {target_idx}) did not occur after "
            f"'{call_assertion.after}' (index {after_idx})",
        )
    return AssertionResult(True, f"'{call_assertion.function}' after '{call_assertion.after}'")


def evaluate_run(test: TestCase, actual_calls: list[ToolCall], latency_ms: float = 0.0, token_count: int = 0) -> RunResult:
    """Evaluate every assertion declared on `test` against one iteration's actual tool calls."""
    results: list[AssertionResult] = []

    for call_assertion in test.assert_calls:
        results.append(check_call(call_assertion, actual_calls))
        results.append(check_after(call_assertion, actual_calls))

    results.extend(check_no_calls(test.assert_no_calls, actual_calls))
    results.append(check_order(test.assert_order, actual_calls))

    failure_reasons = [r.reason for r in results if not r.passed and r.reason]
    passed = all(r.passed for r in results)

    return RunResult(
        passed=passed,
        actual_calls=actual_calls,
        assertion_results=results,
        failure_reasons=failure_reasons,
        latency_ms=latency_ms,
        token_count=token_count,
    )
