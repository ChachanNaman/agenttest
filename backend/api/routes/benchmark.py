"""POST /api/benchmark — run the same suite across multiple models for comparison."""

from __future__ import annotations

import dataclasses
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.parser import SuiteParseError, parse_suite_file
from core.runner import run_suite

router = APIRouter()


class BenchmarkRequest(BaseModel):
    suite_file: str
    models: list[str]
    runs: Optional[int] = None


@router.post("/benchmark")
async def benchmark(req: BenchmarkRequest) -> dict[str, Any]:
    """Run a suite once per model and return comparable pass-rate/latency/accuracy stats."""
    try:
        base_suite = parse_suite_file(req.suite_file)
    except SuiteParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    rows = []
    for model in req.models:
        tests = base_suite.tests
        if req.runs is not None:
            tests = [dataclasses.replace(t, runs=req.runs) for t in tests]
        model_suite = dataclasses.replace(base_suite, model=model, tests=tests)

        results = await run_suite(model_suite)
        total_passes = sum(r.passes for r in results)
        total_runs = sum(r.total for r in results)
        latencies = [r.avg_latency_ms for r in results if r.avg_latency_ms]

        rows.append(
            {
                "model": model,
                "pass_rate": total_passes / total_runs if total_runs else 0.0,
                "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0.0,
                "tests": [
                    {
                        "test_name": r.test_name,
                        "pass_rate": r.pass_rate,
                        "meets_threshold": r.meets_threshold,
                    }
                    for r in results
                ],
            }
        )

    return {"suite": base_suite.suite, "models": rows}
