"""Unit tests for the assertion engine (core/assertions.py)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.adapters.base import ToolCall  # noqa: E402
from core.assertions import (  # noqa: E402
    check_after,
    check_arg,
    check_call,
    check_no_calls,
    check_order,
    evaluate_run,
)
from core.parser import ArgAssertion, CallAssertion, TestCase  # noqa: E402


class CheckArgTests(unittest.TestCase):
    def test_equals_pass_case_insensitive(self) -> None:
        result = check_arg("city", ArgAssertion(equals="Paris"), {"city": "paris"})
        self.assertTrue(result.passed)

    def test_equals_fail(self) -> None:
        result = check_arg("city", ArgAssertion(equals="Paris"), {"city": "London"})
        self.assertFalse(result.passed)
        self.assertIn("expected", result.reason)

    def test_equals_numeric(self) -> None:
        result = check_arg("count", ArgAssertion(equals=3), {"count": 3.0})
        self.assertTrue(result.passed)

    def test_type_pass(self) -> None:
        result = check_arg("id", ArgAssertion(type="string"), {"id": "abc"})
        self.assertTrue(result.passed)

    def test_type_fail(self) -> None:
        result = check_arg("id", ArgAssertion(type="string"), {"id": 123})
        self.assertFalse(result.passed)

    def test_type_bool_not_treated_as_number(self) -> None:
        result = check_arg("flag", ArgAssertion(type="number"), {"flag": True})
        self.assertFalse(result.passed)

    def test_not_null_pass(self) -> None:
        result = check_arg("id", ArgAssertion(not_null=True), {"id": "abc"})
        self.assertTrue(result.passed)

    def test_not_null_fail_missing(self) -> None:
        result = check_arg("id", ArgAssertion(not_null=True), {})
        self.assertFalse(result.passed)

    def test_not_null_fail_none(self) -> None:
        result = check_arg("id", ArgAssertion(not_null=True), {"id": None})
        self.assertFalse(result.passed)

    def test_contains_pass(self) -> None:
        result = check_arg("path", ArgAssertion(contains="pagination"), {"path": "utils/pagination.py"})
        self.assertTrue(result.passed)

    def test_contains_fail(self) -> None:
        result = check_arg("path", ArgAssertion(contains="pagination"), {"path": "utils/auth.py"})
        self.assertFalse(result.passed)

    def test_matches_pass(self) -> None:
        result = check_arg("date", ArgAssertion(matches=r"^\d{4}-\d{2}-\d{2}$"), {"date": "2026-07-15"})
        self.assertTrue(result.passed)

    def test_matches_fail(self) -> None:
        result = check_arg("date", ArgAssertion(matches=r"^\d{4}-\d{2}-\d{2}$"), {"date": "July 15"})
        self.assertFalse(result.passed)


class CheckCallTests(unittest.TestCase):
    def test_matching_call_passes(self) -> None:
        assertion = CallAssertion(function="search_flights", args={"destination": ArgAssertion(equals="Paris")})
        calls = [ToolCall(name="search_flights", arguments={"destination": "Paris"})]
        self.assertTrue(check_call(assertion, calls).passed)

    def test_function_never_called_fails(self) -> None:
        assertion = CallAssertion(function="search_flights")
        result = check_call(assertion, [])
        self.assertFalse(result.passed)
        self.assertIn("never called", result.reason)

    def test_wrong_args_fails(self) -> None:
        assertion = CallAssertion(function="search_flights", args={"destination": ArgAssertion(equals="Paris")})
        calls = [ToolCall(name="search_flights", arguments={"destination": "Tokyo"})]
        self.assertFalse(check_call(assertion, calls).passed)

    def test_any_matching_call_among_multiple_passes(self) -> None:
        assertion = CallAssertion(function="search_flights", args={"destination": ArgAssertion(equals="Paris")})
        calls = [
            ToolCall(name="search_flights", arguments={"destination": "Tokyo"}),
            ToolCall(name="search_flights", arguments={"destination": "Paris"}),
        ]
        self.assertTrue(check_call(assertion, calls).passed)


class CheckNoCallsTests(unittest.TestCase):
    def test_forbidden_call_not_made_passes(self) -> None:
        results = check_no_calls(["send_confirmation"], [ToolCall(name="search_flights", arguments={})])
        self.assertTrue(all(r.passed for r in results))

    def test_forbidden_call_made_fails(self) -> None:
        results = check_no_calls(["send_confirmation"], [ToolCall(name="send_confirmation", arguments={})])
        self.assertFalse(all(r.passed for r in results))


class CheckOrderTests(unittest.TestCase):
    def test_correct_order_passes(self) -> None:
        calls = [ToolCall(name="search_flights", arguments={}), ToolCall(name="book_flight", arguments={})]
        self.assertTrue(check_order(["search_flights", "book_flight"], calls).passed)

    def test_order_with_extra_calls_between_passes(self) -> None:
        calls = [
            ToolCall(name="search_flights", arguments={}),
            ToolCall(name="check_status", arguments={}),
            ToolCall(name="book_flight", arguments={}),
        ]
        self.assertTrue(check_order(["search_flights", "book_flight"], calls).passed)

    def test_incorrect_order_fails(self) -> None:
        calls = [ToolCall(name="book_flight", arguments={}), ToolCall(name="search_flights", arguments={})]
        self.assertFalse(check_order(["search_flights", "book_flight"], calls).passed)

    def test_empty_order_always_passes(self) -> None:
        self.assertTrue(check_order([], []).passed)


class CheckAfterTests(unittest.TestCase):
    def test_after_satisfied_passes(self) -> None:
        assertion = CallAssertion(function="book_flight", after="search_flights")
        calls = [ToolCall(name="search_flights", arguments={}), ToolCall(name="book_flight", arguments={})]
        self.assertTrue(check_after(assertion, calls).passed)

    def test_after_violated_fails(self) -> None:
        assertion = CallAssertion(function="book_flight", after="search_flights")
        calls = [ToolCall(name="book_flight", arguments={}), ToolCall(name="search_flights", arguments={})]
        self.assertFalse(check_after(assertion, calls).passed)

    def test_no_after_constraint_passes(self) -> None:
        assertion = CallAssertion(function="book_flight")
        self.assertTrue(check_after(assertion, []).passed)


class EvaluateRunTests(unittest.TestCase):
    def test_full_passing_run(self) -> None:
        test = TestCase(
            name="search before booking",
            assert_calls=[
                CallAssertion(function="search_flights", args={"destination": ArgAssertion(equals="Paris")}),
                CallAssertion(function="book_flight", after="search_flights"),
            ],
            assert_no_calls=["send_confirmation"],
            assert_order=["search_flights", "book_flight"],
        )
        calls = [
            ToolCall(name="search_flights", arguments={"destination": "Paris"}),
            ToolCall(name="book_flight", arguments={"flight_id": "F1"}),
        ]
        result = evaluate_run(test, calls)
        self.assertTrue(result.passed)
        self.assertEqual(result.failure_reasons, [])

    def test_failing_run_records_reasons(self) -> None:
        test = TestCase(
            name="search before booking",
            assert_calls=[CallAssertion(function="search_flights")],
            assert_no_calls=["send_confirmation"],
        )
        calls = [ToolCall(name="send_confirmation", arguments={})]
        result = evaluate_run(test, calls)
        self.assertFalse(result.passed)
        self.assertTrue(len(result.failure_reasons) >= 1)


if __name__ == "__main__":
    unittest.main()
