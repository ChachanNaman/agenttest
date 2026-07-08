"""WebSocket handler for live-streamed test runs at /ws/run."""

from __future__ import annotations

import json
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from core import storage
from core.parser import SuiteParseError, parse_suite_file
from core.runner import run_suite


async def handle_run_socket(websocket: WebSocket) -> None:
    """Accept a WebSocket connection, run the requested suite, and stream progress events.

    Always closes the socket before returning — the client's connection
    status drives its "running" UI state, so an implicitly-left-open
    socket would strand the dashboard mid-run indefinitely.
    """
    await websocket.accept()
    try:
        raw = await websocket.receive_text()
        request = json.loads(raw)
        suite_file = request["suite_file"]

        try:
            suite = parse_suite_file(suite_file)
        except (SuiteParseError, KeyError) as exc:
            await websocket.send_json({"type": "error", "message": str(exc)})
            return

        storage.register_suite(suite.suite, suite_file)

        async def on_progress(event: dict[str, Any]) -> None:
            await websocket.send_json(event)

        results = await run_suite(suite, on_progress=on_progress)

        for result in results:
            storage.save_test_result(suite.suite, suite.model, result)

    except WebSocketDisconnect:
        return
    except Exception as exc:  # noqa: BLE001 — surface any failure to the connected client
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
        except RuntimeError:
            pass
    finally:
        try:
            await websocket.close()
        except RuntimeError:
            pass
