"""YAML test suite parser: converts agenttest.yaml files into typed dataclasses."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

DEFAULT_RUNS = 10
DEFAULT_PASS_THRESHOLD = 0.8
SUPPORTED_VERSIONS = {"1.0"}


class SuiteParseError(ValueError):
    """Raised when an agenttest YAML file is malformed or missing required fields."""


@dataclass
class ArgAssertion:
    """A single assertion applied to one tool-call argument."""

    equals: Optional[Any] = None
    type: Optional[str] = None
    not_null: Optional[bool] = None
    contains: Optional[str] = None
    matches: Optional[str] = None

    @staticmethod
    def from_dict(raw: dict) -> "ArgAssertion":
        if not isinstance(raw, dict):
            raise SuiteParseError(f"argument assertion must be a mapping, got: {raw!r}")
        known = {"equals", "type", "not_null", "contains", "matches"}
        unknown = set(raw.keys()) - known
        if unknown:
            raise SuiteParseError(f"unknown argument assertion keys: {sorted(unknown)}")
        return ArgAssertion(
            equals=raw.get("equals"),
            type=raw.get("type"),
            not_null=raw.get("not_null"),
            contains=raw.get("contains"),
            matches=raw.get("matches"),
        )


@dataclass
class CallAssertion:
    """Asserts that a specific tool/function was called, optionally with argument checks."""

    function: str
    args: dict[str, ArgAssertion] = field(default_factory=dict)
    after: Optional[str] = None

    @staticmethod
    def from_dict(raw: dict) -> "CallAssertion":
        if "function" not in raw:
            raise SuiteParseError(f"call assertion missing required field 'function': {raw!r}")
        args_raw = raw.get("args", {})
        args = {name: ArgAssertion.from_dict(a) for name, a in args_raw.items()}
        return CallAssertion(function=raw["function"], args=args, after=raw.get("after"))


@dataclass
class ToolParam:
    """A single parameter in a tool's schema."""

    name: str
    type: str = "string"
    description: str = ""


@dataclass
class ToolDef:
    """A tool/function definition exposed to the model under test."""

    name: str
    description: str = ""
    parameters: list[ToolParam] = field(default_factory=list)
    required: list[str] = field(default_factory=list)

    @staticmethod
    def from_dict(raw: dict) -> "ToolDef":
        if "name" not in raw:
            raise SuiteParseError(f"tool definition missing required field 'name': {raw!r}")
        params_raw = raw.get("parameters", {})
        params = [
            ToolParam(
                name=pname,
                type=pdef.get("type", "string") if isinstance(pdef, dict) else "string",
                description=pdef.get("description", "") if isinstance(pdef, dict) else "",
            )
            for pname, pdef in params_raw.items()
        ]
        return ToolDef(
            name=raw["name"],
            description=raw.get("description", ""),
            parameters=params,
            required=raw.get("required", []),
        )

    def to_openai_schema(self) -> dict:
        """Render as an OpenAI-style function-calling tool schema."""
        properties = {
            p.name: {"type": p.type, "description": p.description} for p in self.parameters
        }
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": self.required,
                },
            },
        }


@dataclass
class ConversationTurn:
    """One turn of a multi-turn conversation test."""

    role: str
    message: str
    assert_calls: list[str] = field(default_factory=list)

    @staticmethod
    def from_dict(raw: dict) -> "ConversationTurn":
        if "message" not in raw:
            raise SuiteParseError(f"conversation turn missing required field 'message': {raw!r}")
        return ConversationTurn(
            role=raw.get("role", "user"),
            message=raw["message"],
            assert_calls=raw.get("assert_calls", []),
        )


@dataclass
class TestCase:
    """A single test: either single-turn (message) or multi-turn (conversation)."""

    name: str
    runs: int = DEFAULT_RUNS
    pass_threshold: float = DEFAULT_PASS_THRESHOLD
    message: Optional[str] = None
    conversation: list[ConversationTurn] = field(default_factory=list)
    assert_calls: list[CallAssertion] = field(default_factory=list)
    assert_no_calls: list[str] = field(default_factory=list)
    assert_order: list[str] = field(default_factory=list)

    @property
    def is_multi_turn(self) -> bool:
        return bool(self.conversation)

    @staticmethod
    def from_dict(raw: dict) -> "TestCase":
        if "name" not in raw:
            raise SuiteParseError(f"test case missing required field 'name': {raw!r}")
        has_message = "message" in raw
        has_conversation = "conversation" in raw
        if has_message == has_conversation:
            raise SuiteParseError(
                f"test '{raw['name']}' must define exactly one of 'message' or 'conversation'"
            )

        conversation = [ConversationTurn.from_dict(t) for t in raw.get("conversation", [])]
        assert_calls = [CallAssertion.from_dict(c) for c in raw.get("assert_calls", [])]

        runs = raw.get("runs", DEFAULT_RUNS)
        if not isinstance(runs, int) or runs < 1:
            raise SuiteParseError(f"test '{raw['name']}': 'runs' must be a positive integer")

        threshold = raw.get("pass_threshold", DEFAULT_PASS_THRESHOLD)
        if not isinstance(threshold, (int, float)) or not (0.0 <= threshold <= 1.0):
            raise SuiteParseError(
                f"test '{raw['name']}': 'pass_threshold' must be between 0.0 and 1.0"
            )

        return TestCase(
            name=raw["name"],
            runs=runs,
            pass_threshold=float(threshold),
            message=raw.get("message"),
            conversation=conversation,
            assert_calls=assert_calls,
            assert_no_calls=raw.get("assert_no_calls", []),
            assert_order=raw.get("assert_order", []),
        )


@dataclass
class TestSuite:
    """A full agenttest.yaml file: metadata, tool schema, system prompt, and tests."""

    version: str
    suite: str
    system_prompt: str
    model: str
    tools: list[ToolDef] = field(default_factory=list)
    tests: list[TestCase] = field(default_factory=list)
    source_path: Optional[str] = None

    def tool_by_name(self, name: str) -> Optional[ToolDef]:
        return next((t for t in self.tools if t.name == name), None)


def _require(raw: dict, key: str, context: str) -> Any:
    if key not in raw:
        raise SuiteParseError(f"{context} missing required field '{key}'")
    return raw[key]


def parse_suite_dict(raw: dict, source_path: Optional[str] = None) -> TestSuite:
    """Convert a parsed YAML mapping into a validated TestSuite."""
    if not isinstance(raw, dict):
        raise SuiteParseError("suite file must contain a YAML mapping at the top level")

    version = str(_require(raw, "version", "suite"))
    if version not in SUPPORTED_VERSIONS:
        raise SuiteParseError(f"unsupported suite version '{version}', expected one of {SUPPORTED_VERSIONS}")

    suite_name = _require(raw, "suite", "suite")
    system_prompt = raw.get("system_prompt", "")
    model = _require(raw, "model", "suite")

    tools_raw = raw.get("tools", [])
    tools = [ToolDef.from_dict(t) for t in tools_raw]

    tests_raw = raw.get("tests", [])
    if not tests_raw:
        raise SuiteParseError(f"suite '{suite_name}' defines no tests")
    tests = [TestCase.from_dict(t) for t in tests_raw]

    known_tools = {t.name for t in tools}
    for test in tests:
        for call in test.assert_calls:
            if known_tools and call.function not in known_tools:
                raise SuiteParseError(
                    f"test '{test.name}' asserts unknown tool '{call.function}' "
                    f"(declared tools: {sorted(known_tools)})"
                )

    return TestSuite(
        version=version,
        suite=suite_name,
        system_prompt=system_prompt,
        model=model,
        tools=tools,
        tests=tests,
        source_path=source_path,
    )


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _resolve_suite_path(path: str | Path) -> Path:
    """Resolve a suite path against cwd first, falling back to the project root.

    The API/CLI may be launched with cwd set to either the repo root or
    `backend/`, so a relative path like `tests/examples/booking.yaml` typed
    into the dashboard needs to resolve consistently regardless of which.
    """
    candidate = Path(path)
    if candidate.is_absolute() or candidate.exists():
        return candidate
    fallback = PROJECT_ROOT / candidate
    return fallback if fallback.exists() else candidate


def parse_suite_file(path: str | Path) -> TestSuite:
    """Read and parse an agenttest YAML file from disk."""
    file_path = _resolve_suite_path(path)
    if not file_path.exists():
        raise SuiteParseError(f"suite file not found: {file_path}")
    try:
        raw = yaml.safe_load(file_path.read_text())
    except yaml.YAMLError as exc:
        raise SuiteParseError(f"invalid YAML in {file_path}: {exc}") from exc
    return parse_suite_dict(raw, source_path=str(file_path))


_ARG_TYPE_MAP = {
    "string": str,
    "number": (int, float),
    "boolean": bool,
    "object": dict,
    "array": list,
}


def python_type_for(arg_type: str) -> Any:
    """Map an agenttest YAML type name to a Python type (or tuple of types)."""
    if arg_type not in _ARG_TYPE_MAP:
        raise SuiteParseError(f"unknown argument type '{arg_type}'")
    return _ARG_TYPE_MAP[arg_type]


_REGEX_CACHE: dict[str, re.Pattern] = {}


def compiled_regex(pattern: str) -> re.Pattern:
    """Compile (and cache) a regex pattern used by 'matches' assertions."""
    if pattern not in _REGEX_CACHE:
        try:
            _REGEX_CACHE[pattern] = re.compile(pattern)
        except re.error as exc:
            raise SuiteParseError(f"invalid regex pattern '{pattern}': {exc}") from exc
    return _REGEX_CACHE[pattern]
