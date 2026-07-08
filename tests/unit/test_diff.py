"""Unit tests for the semantic diff engine (core/diff.py)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.adapters.base import ToolCall  # noqa: E402
from core.diff import diff_args, diff_tool_calls  # noqa: E402


class DiffArgsTests(unittest.TestCase):
    def test_matching_args_all_match(self) -> None:
        diffs = diff_args({"city": "Paris"}, {"city": "paris"})
        self.assertEqual(len(diffs), 1)
        self.assertEqual(diffs[0].status, "match")

    def test_mismatched_value(self) -> None:
        diffs = diff_args({"city": "Paris"}, {"city": "Tokyo"})
        self.assertEqual(diffs[0].status, "mismatch")
        self.assertEqual(diffs[0].expected_value, "Paris")
        self.assertEqual(diffs[0].actual_value, "Tokyo")

    def test_missing_key(self) -> None:
        diffs = diff_args({"city": "Paris"}, {})
        self.assertEqual(diffs[0].status, "missing")

    def test_extra_key(self) -> None:
        diffs = diff_args({}, {"extra_field": "value"})
        self.assertEqual(diffs[0].status, "extra")

    def test_numeric_equality_across_int_float(self) -> None:
        diffs = diff_args({"count": 3}, {"count": 3.0})
        self.assertEqual(diffs[0].status, "match")


class DiffToolCallsTests(unittest.TestCase):
    def test_identical_calls_produce_no_differences(self) -> None:
        expected = [ToolCall(name="search_flights", arguments={"city": "Paris"})]
        actual = [ToolCall(name="search_flights", arguments={"city": "Paris"})]
        result = diff_tool_calls(expected, actual)
        self.assertFalse(result.has_differences)
        self.assertEqual(result.call_diffs[0].status, "match")

    def test_mismatched_args_detected(self) -> None:
        expected = [ToolCall(name="search_flights", arguments={"city": "Paris"})]
        actual = [ToolCall(name="search_flights", arguments={"city": "Tokyo"})]
        result = diff_tool_calls(expected, actual)
        self.assertTrue(result.has_differences)
        self.assertEqual(result.call_diffs[0].status, "arg_mismatch")

    def test_missing_call_detected(self) -> None:
        expected = [ToolCall(name="book_flight", arguments={})]
        actual: list[ToolCall] = []
        result = diff_tool_calls(expected, actual)
        self.assertEqual(result.call_diffs[0].status, "missing")

    def test_extra_call_detected(self) -> None:
        expected: list[ToolCall] = []
        actual = [ToolCall(name="send_confirmation", arguments={"id": "1"})]
        result = diff_tool_calls(expected, actual)
        self.assertEqual(result.call_diffs[0].status, "extra")
        self.assertEqual(result.call_diffs[0].function, "send_confirmation")

    def test_matches_by_name_positionally_among_duplicates(self) -> None:
        expected = [
            ToolCall(name="search_flights", arguments={"city": "Paris"}),
            ToolCall(name="search_flights", arguments={"city": "Tokyo"}),
        ]
        actual = [
            ToolCall(name="search_flights", arguments={"city": "Paris"}),
            ToolCall(name="search_flights", arguments={"city": "Tokyo"}),
        ]
        result = diff_tool_calls(expected, actual)
        self.assertFalse(result.has_differences)
        self.assertEqual(len(result.call_diffs), 2)


if __name__ == "__main__":
    unittest.main()
