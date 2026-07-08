"""POST /api/run and GET /api/runs, GET /api/runs/{run_id}."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core import storage
from core.parser import SuiteParseError, parse_suite_file
from core.runner import TestResult, run_suite

router = APIRouter()


class RunRequest(BaseModel):
    suite_file: str


def serialize_test_result(result: TestResult) -> dict[str, Any]:
    return {
        "test_name": result.test_name,
        "passes": result.passes,
        "total": result.total,
        "pass_rate": result.pass_rate,
        "meets_threshold": result.meets_threshold,
        "verdict": result.verdict,
        "ci_lower": result.ci_lower,
        "ci_upper": result.ci_upper,
        "avg_latency_ms": result.avg_latency_ms,
        "failures": [
            {"iteration": i, "reasons": r.failure_reasons}
            for i, r in enumerate(result.run_results)
            if not r.passed
        ],
    }


@router.post("/run")
async def trigger_run(req: RunRequest) -> dict[str, Any]:
    """Run every test in a suite file synchronously and persist the results."""
    try:
        suite = parse_suite_file(req.suite_file)
    except SuiteParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    storage.register_suite(suite.suite, req.suite_file)
    results = await run_suite(suite)

    run_ids = [storage.save_test_result(suite.suite, suite.model, r) for r in results]

    return {
        "run_id": run_ids[-1] if run_ids else None,
        "suite": suite.suite,
        "results": [serialize_test_result(r) for r in results],
    }


@router.get("/runs")
async def list_runs(suite: Optional[str] = None) -> list[dict[str, Any]]:
    """List all persisted run summaries, optionally filtered by suite name."""
    return storage.get_all_runs(suite_name=suite)


@router.get("/runs/{run_id}")
async def get_run(run_id: int) -> dict[str, Any]:
    """Fetch a single run's summary and all of its iterations."""
    run = storage.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    return run
