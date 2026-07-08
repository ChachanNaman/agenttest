"""GET/POST /api/snapshots/{suite_name}/{test_name} — saved tool-call argument schemas."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core import storage

router = APIRouter()


class SnapshotRequest(BaseModel):
    function_name: str
    arg_schema: dict[str, Any]


@router.get("/snapshots/{suite_name}/{test_name}")
async def get_snapshot(suite_name: str, test_name: str, function_name: str) -> dict[str, Any]:
    """Fetch the most recently saved argument schema snapshot for a function in a test."""
    snapshot = storage.get_snapshot(suite_name, test_name, function_name)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="no snapshot found")
    return snapshot


@router.post("/snapshots/{suite_name}/{test_name}")
async def save_snapshot(suite_name: str, test_name: str, req: SnapshotRequest) -> dict[str, Any]:
    """Save a new argument schema snapshot for a function in a test."""
    snapshot_id = storage.save_snapshot(suite_name, test_name, req.function_name, req.arg_schema)
    return {"id": snapshot_id}
