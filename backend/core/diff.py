"""Semantic diff engine: structurally diffs two sets of tool calls (not string diffing)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from .adapters.base import ToolCall

ArgDiffStatus = Literal["match", "mismatch", "missing", "extra"]
CallDiffStatus = Literal["match", "arg_mismatch", "missing", "extra"]


@dataclass
class ArgDiff:
    """Diff of a single argument between an expected and an actual tool call."""

    key: str
    expected_value: Any
    actual_value: Any
    status: ArgDiffStatus


@dataclass
class CallDiff:
    """Diff of a single tool call, including per-argument diffs."""

    function: str
    status: CallDiffStatus
    arg_diffs: list[ArgDiff] = field(default_factory=list)


@dataclass
class DiffResult:
    """Full structural diff between an expected and actual sequence of tool calls."""

    call_diffs: list[CallDiff] = field(default_factory=list)

    @property
    def has_differences(self) -> bool:
        return any(cd.status != "match" for cd in self.call_diffs)


def diff_args(expected_args: dict[str, Any], actual_args: dict[str, Any]) -> list[ArgDiff]:
    """Diff two argument dicts key by key, reporting match/mismatch/missing/extra."""
    diffs: list[ArgDiff] = []
    all_keys = sorted(set(expected_args.keys()) | set(actual_args.keys()))

    for key in all_keys:
        has_expected = key in expected_args
        has_actual = key in actual_args
        expected_value = expected_args.get(key)
        actual_value = actual_args.get(key)

        if has_expected and not has_actual:
            diffs.append(ArgDiff(key, expected_value, None, "missing"))
        elif has_actual and not has_expected:
            diffs.append(ArgDiff(key, None, actual_value, "extra"))
        elif _equal(expected_value, actual_value):
            diffs.append(ArgDiff(key, expected_value, actual_value, "match"))
        else:
            diffs.append(ArgDiff(key, expected_value, actual_value, "mismatch"))

    return diffs


def _equal(a: Any, b: Any) -> bool:
    if isinstance(a, str) and isinstance(b, str):
        return a.strip().lower() == b.strip().lower()
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return float(a) == float(b)
    return a == b


def diff_tool_calls(expected_calls: list[ToolCall], actual_calls: list[ToolCall]) -> DiffResult:
    """Structurally diff an expected sequence of tool calls against the actual sequence.

    Matches calls positionally by function name (first unmatched actual call
    with the same name), then diffs their arguments. Expected calls with no
    matching actual call are reported "missing"; actual calls with no
    matching expected call are reported "extra".
    """
    remaining_actual = list(actual_calls)
    call_diffs: list[CallDiff] = []

    for expected in expected_calls:
        match_idx = next(
            (i for i, c in enumerate(remaining_actual) if c.name == expected.name), None
        )
        if match_idx is None:
            call_diffs.append(CallDiff(function=expected.name, status="missing"))
            continue

        actual = remaining_actual.pop(match_idx)
        arg_diffs = diff_args(expected.arguments, actual.arguments)
        status: CallDiffStatus = (
            "match" if all(d.status == "match" for d in arg_diffs) else "arg_mismatch"
        )
        call_diffs.append(CallDiff(function=expected.name, status=status, arg_diffs=arg_diffs))

    for leftover in remaining_actual:
        call_diffs.append(
            CallDiff(
                function=leftover.name,
                status="extra",
                arg_diffs=[ArgDiff(k, None, v, "extra") for k, v in leftover.arguments.items()],
            )
        )

    return DiffResult(call_diffs=call_diffs)
