"""GET /api/history/{suite_name}/{test_name} and GET /api/flakiness/{suite_name}."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from core import storage

router = APIRouter()


@router.get("/history/{suite_name}/{test_name}")
async def get_history(suite_name: str, test_name: str, limit: int = Query(default=50, le=500)) -> list[dict[str, Any]]:
    """Time-series pass-rate/latency history for one test, for trend charts."""
    return storage.get_history(suite_name, test_name, limit=limit)


@router.get("/flakiness/{suite_name}")
async def get_flakiness(suite_name: str) -> list[dict[str, Any]]:
    """Flakiness scores for every test that has run history in this suite."""
    return storage.get_flakiness_report(suite_name)
