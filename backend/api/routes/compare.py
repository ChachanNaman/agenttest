"""POST /api/compare — regression comparison between a baseline and candidate configuration."""

from __future__ import annotations

import dataclasses
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core import storage
from core.parser import SuiteParseError, TestSuite, parse_suite_file
from core.runner import TestResult, run_suite
from core.stats import detect_regression

router = APIRouter()


class VariantConfig(BaseModel):
    label: str
    system_prompt: Optional[str] = None
    model: Optional[str] = None


class CompareRequest(BaseModel):
    suite_file: str
    baseline: VariantConfig
    candidate: VariantConfig
    runs: Optional[int] = None


def _apply_variant(suite: TestSuite, variant: VariantConfig, runs_override: Optional[int]) -> TestSuite:
    tests = suite.tests
    if runs_override is not None:
        tests = [dataclasses.replace(t, runs=runs_override) for t in tests]
    return dataclasses.replace(
        suite,
        system_prompt=variant.system_prompt if variant.system_prompt is not None else suite.system_prompt,
        model=variant.model if variant.model is not None else suite.model,
        tests=tests,
    )


def _index_by_name(results: list[TestResult]) -> dict[str, TestResult]:
    return {r.test_name: r for r in results}


@router.post("/compare")
async def compare(req: CompareRequest) -> dict[str, Any]:
    """Run a suite under baseline and candidate configs and report per-test regressions."""
    try:
        suite = parse_suite_file(req.suite_file)
    except SuiteParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    baseline_suite = _apply_variant(suite, req.baseline, req.runs)
    candidate_suite = _apply_variant(suite, req.candidate, req.runs)

    baseline_results = _index_by_name(await run_suite(baseline_suite))
    candidate_results = _index_by_name(await run_suite(candidate_suite))

    rows = []
    has_regression = False
    for test_name in baseline_results:
        base = baseline_results[test_name]
        cand = candidate_results.get(test_name)
        if cand is None:
            continue
        regression = detect_regression(base.passes, base.total, cand.passes, cand.total)
        if regression.is_regression:
            has_regression = True
        rows.append(
            {
                "test_name": test_name,
                "baseline_pass_rate": regression.baseline_pass_rate,
                "candidate_pass_rate": regression.candidate_pass_rate,
                "delta": regression.delta,
                "p_value": regression.p_value,
                "is_regression": regression.is_regression,
                "verdict": regression.verdict,
            }
        )

    storage.save_comparison(suite.suite, req.baseline.label, req.candidate.label, rows, has_regression)

    return {
        "suite": suite.suite,
        "baseline_label": req.baseline.label,
        "candidate_label": req.candidate.label,
        "has_regression": has_regression,
        "results": rows,
    }
