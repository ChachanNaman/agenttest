"""Unit tests for the YAML suite parser (core/parser.py)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.parser import SuiteParseError, parse_suite_dict, parse_suite_file  # noqa: E402

VALID_SINGLE_TURN = {
    "version": "1.0",
    "suite": "Test Suite",
    "system_prompt": "You are a helpful assistant.",
    "model": "llama-3.3-70b-versatile",
    "tools": [
        {
            "name": "search_flights",
            "description": "Search flights",
            "parameters": {"destination": {"type": "string"}},
            "required": ["destination"],
        }
    ],
    "tests": [
        {
            "name": "basic search",
            "message": "find a flight to Paris",
            "runs": 10,
            "pass_threshold": 0.8,
            "assert_calls": [{"function": "search_flights", "args": {"destination": {"equals": "Paris"}}}],
        }
    ],
}

VALID_CONVERSATION = {
    "version": "1.0",
    "suite": "Conversation Suite",
    "system_prompt": "You are a helpful assistant.",
    "model": "llama-3.3-70b-versatile",
    "tools": [],
    "tests": [
        {
            "name": "multi-turn",
            "conversation": [
                {"role": "user", "message": "book a flight", "assert_calls": ["search_flights"]},
                {"role": "user", "message": "cancel it", "assert_calls": ["cancel_booking"]},
            ],
            "runs": 5,
        }
    ],
}


class ParseValidSuitesTests(unittest.TestCase):
    def test_single_turn_suite_parses(self) -> None:
        suite = parse_suite_dict(VALID_SINGLE_TURN)
        self.assertEqual(suite.suite, "Test Suite")
        self.assertEqual(len(suite.tests), 1)
        self.assertEqual(suite.tests[0].message, "find a flight to Paris")
        self.assertFalse(suite.tests[0].is_multi_turn)

    def test_conversation_suite_parses(self) -> None:
        suite = parse_suite_dict(VALID_CONVERSATION)
        test = suite.tests[0]
        self.assertTrue(test.is_multi_turn)
        self.assertEqual(len(test.conversation), 2)
        self.assertEqual(test.conversation[0].assert_calls, ["search_flights"])

    def test_defaults_applied(self) -> None:
        suite = parse_suite_dict(VALID_CONVERSATION)
        self.assertEqual(suite.tests[0].pass_threshold, 0.8)

    def test_tool_openai_schema_shape(self) -> None:
        suite = parse_suite_dict(VALID_SINGLE_TURN)
        schema = suite.tools[0].to_openai_schema()
        self.assertEqual(schema["type"], "function")
        self.assertEqual(schema["function"]["name"], "search_flights")
        self.assertIn("destination", schema["function"]["parameters"]["properties"])


class ParseErrorTests(unittest.TestCase):
    def test_missing_version_raises(self) -> None:
        raw = {k: v for k, v in VALID_SINGLE_TURN.items() if k != "version"}
        with self.assertRaises(SuiteParseError):
            parse_suite_dict(raw)

    def test_missing_suite_name_raises(self) -> None:
        raw = {k: v for k, v in VALID_SINGLE_TURN.items() if k != "suite"}
        with self.assertRaises(SuiteParseError):
            parse_suite_dict(raw)

    def test_no_tests_raises(self) -> None:
        raw = {**VALID_SINGLE_TURN, "tests": []}
        with self.assertRaises(SuiteParseError):
            parse_suite_dict(raw)

    def test_test_missing_message_and_conversation_raises(self) -> None:
        raw = {**VALID_SINGLE_TURN, "tests": [{"name": "bad test", "runs": 5}]}
        with self.assertRaises(SuiteParseError):
            parse_suite_dict(raw)

    def test_test_with_both_message_and_conversation_raises(self) -> None:
        bad_test = {**VALID_SINGLE_TURN["tests"][0], "conversation": VALID_CONVERSATION["tests"][0]["conversation"]}
        raw = {**VALID_SINGLE_TURN, "tests": [bad_test]}
        with self.assertRaises(SuiteParseError):
            parse_suite_dict(raw)

    def test_unknown_asserted_tool_raises(self) -> None:
        bad_test = {**VALID_SINGLE_TURN["tests"][0], "assert_calls": [{"function": "nonexistent_tool"}]}
        raw = {**VALID_SINGLE_TURN, "tests": [bad_test]}
        with self.assertRaises(SuiteParseError):
            parse_suite_dict(raw)

    def test_invalid_pass_threshold_raises(self) -> None:
        bad_test = {**VALID_SINGLE_TURN["tests"][0], "pass_threshold": 1.5}
        raw = {**VALID_SINGLE_TURN, "tests": [bad_test]}
        with self.assertRaises(SuiteParseError):
            parse_suite_dict(raw)

    def test_unsupported_version_raises(self) -> None:
        raw = {**VALID_SINGLE_TURN, "version": "2.0"}
        with self.assertRaises(SuiteParseError):
            parse_suite_dict(raw)

    def test_missing_file_raises(self) -> None:
        with self.assertRaises(SuiteParseError):
            parse_suite_file("/nonexistent/path/suite.yaml")


class ParseFileTests(unittest.TestCase):
    def test_parses_from_disk(self) -> None:
        import yaml

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.safe_dump(VALID_SINGLE_TURN, f)
            path = f.name
        try:
            suite = parse_suite_file(path)
            self.assertEqual(suite.suite, "Test Suite")
        finally:
            Path(path).unlink()


if __name__ == "__main__":
    unittest.main()
