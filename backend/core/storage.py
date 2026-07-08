"""SQLite storage layer. Raw SQL only, no ORM."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator, Optional

from .assertions import RunResult

if TYPE_CHECKING:
    from .runner import TestResult

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Anchored to the project root (not cwd) so the CLI and the API server land on the
# same database file regardless of which directory each was launched from.
DEFAULT_DB_PATH = str(PROJECT_ROOT / "agenttest.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS suites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    file_path TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    suite_name TEXT NOT NULL,
    test_name TEXT NOT NULL,
    model TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    total_iterations INTEGER NOT NULL,
    passes INTEGER NOT NULL,
    pass_rate REAL NOT NULL,
    threshold REAL NOT NULL,
    meets_threshold INTEGER NOT NULL,
    avg_latency_ms REAL,
    ci_lower REAL,
    ci_upper REAL,
    flakiness_score REAL
);

CREATE TABLE IF NOT EXISTS iterations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES runs(id),
    iteration_number INTEGER NOT NULL,
    passed INTEGER NOT NULL,
    actual_calls TEXT NOT NULL,
    failure_reasons TEXT NOT NULL,
    latency_ms REAL,
    token_count INTEGER
);

CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    suite_name TEXT NOT NULL,
    test_name TEXT NOT NULL,
    function_name TEXT NOT NULL,
    arg_schema TEXT NOT NULL,
    captured_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS comparisons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    suite_name TEXT NOT NULL,
    baseline_label TEXT NOT NULL,
    candidate_label TEXT NOT NULL,
    run_at TEXT NOT NULL,
    results TEXT NOT NULL,
    has_regression INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_runs_suite_test ON runs(suite_name, test_name);
CREATE INDEX IF NOT EXISTS idx_iterations_run_id ON iterations(run_id);
"""

_local = threading.local()


def _db_path() -> str:
    """Resolve the database path, anchoring any relative DATABASE_PATH to the project root.

    A relative value (including the one shipped in .env.example) must resolve the
    same way regardless of whether the CLI or the API server's cwd launched it from
    the repo root or from backend/ — otherwise the two processes silently split
    into two separate SQLite files.
    """
    raw = os.environ.get("DATABASE_PATH")
    if not raw:
        return DEFAULT_DB_PATH
    candidate = Path(raw)
    return str(candidate) if candidate.is_absolute() else str(PROJECT_ROOT / candidate)


def _connect(db_path: Optional[str] = None) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path or _db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_connection(db_path: Optional[str] = None) -> Iterator[sqlite3.Connection]:
    """Context-managed SQLite connection with commit-on-success / rollback-on-error."""
    conn = _connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Optional[str] = None) -> None:
    """Create all tables (idempotent)."""
    with get_connection(db_path) as conn:
        conn.executescript(_SCHEMA)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tool_calls_to_json(calls: list) -> str:
    return json.dumps([{"name": c.name, "arguments": c.arguments} for c in calls])


def register_suite(name: str, file_path: str, db_path: Optional[str] = None) -> int:
    """Insert or update a suite record; returns the suite id."""
    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO suites (name, file_path, created_at) VALUES (?, ?, ?) "
            "ON CONFLICT(name) DO UPDATE SET file_path = excluded.file_path",
            (name, file_path, _now()),
        )
        row = conn.execute("SELECT id FROM suites WHERE name = ?", (name,)).fetchone()
        return int(row["id"])


def save_run(
    suite_name: str,
    test_name: str,
    model: str,
    total_iterations: int,
    passes: int,
    pass_rate: float,
    threshold: float,
    meets_threshold: bool,
    avg_latency_ms: Optional[float] = None,
    ci_lower: Optional[float] = None,
    ci_upper: Optional[float] = None,
    flakiness: Optional[float] = None,
    started_at: Optional[str] = None,
    completed_at: Optional[str] = None,
    db_path: Optional[str] = None,
) -> int:
    """Persist a completed test run's summary statistics. Returns the run id."""
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO runs (
                suite_name, test_name, model, started_at, completed_at,
                total_iterations, passes, pass_rate, threshold, meets_threshold,
                avg_latency_ms, ci_lower, ci_upper, flakiness_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                suite_name,
                test_name,
                model,
                started_at or _now(),
                completed_at or _now(),
                total_iterations,
                passes,
                pass_rate,
                threshold,
                int(meets_threshold),
                avg_latency_ms,
                ci_lower,
                ci_upper,
                flakiness,
            ),
        )
        return int(cursor.lastrowid)


def save_iteration(
    run_id: int, iteration_number: int, run_result: RunResult, db_path: Optional[str] = None
) -> int:
    """Persist a single iteration's outcome, linked to its parent run."""
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO iterations (
                run_id, iteration_number, passed, actual_calls, failure_reasons, latency_ms, token_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                iteration_number,
                int(run_result.passed),
                _tool_calls_to_json(run_result.actual_calls),
                json.dumps(run_result.failure_reasons),
                run_result.latency_ms,
                run_result.token_count,
            ),
        )
        return int(cursor.lastrowid)


def get_run(run_id: int, db_path: Optional[str] = None) -> Optional[dict[str, Any]]:
    """Fetch a single run summary along with all of its iterations."""
    with get_connection(db_path) as conn:
        run_row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if run_row is None:
            return None
        iter_rows = conn.execute(
            "SELECT * FROM iterations WHERE run_id = ? ORDER BY iteration_number", (run_id,)
        ).fetchall()
        run = dict(run_row)
        run["iterations"] = [dict(r) for r in iter_rows]
        return run


def get_all_runs(suite_name: Optional[str] = None, db_path: Optional[str] = None) -> list[dict[str, Any]]:
    """List all run summaries, optionally filtered to one suite, most recent first."""
    with get_connection(db_path) as conn:
        if suite_name:
            rows = conn.execute(
                "SELECT * FROM runs WHERE suite_name = ? ORDER BY id DESC", (suite_name,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM runs ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]


def get_history(
    suite_name: str, test_name: str, limit: int = 50, db_path: Optional[str] = None
) -> list[dict[str, Any]]:
    """Time-ordered pass-rate/latency history for one test, for trend charts."""
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM runs WHERE suite_name = ? AND test_name = ?
            ORDER BY id DESC LIMIT ?
            """,
            (suite_name, test_name, limit),
        ).fetchall()
        return list(reversed([dict(r) for r in rows]))


def save_snapshot(
    suite_name: str, test_name: str, function_name: str, arg_schema: dict, db_path: Optional[str] = None
) -> int:
    """Persist an observed argument schema for a tool call, for future contract comparisons."""
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO snapshots (suite_name, test_name, function_name, arg_schema, captured_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (suite_name, test_name, function_name, json.dumps(arg_schema), _now()),
        )
        return int(cursor.lastrowid)


def get_snapshot(
    suite_name: str, test_name: str, function_name: str, db_path: Optional[str] = None
) -> Optional[dict[str, Any]]:
    """Fetch the most recent snapshot for a given suite/test/function combination."""
    with get_connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT * FROM snapshots
            WHERE suite_name = ? AND test_name = ? AND function_name = ?
            ORDER BY id DESC LIMIT 1
            """,
            (suite_name, test_name, function_name),
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["arg_schema"] = json.loads(result["arg_schema"])
        return result


def save_comparison(
    suite_name: str,
    baseline_label: str,
    candidate_label: str,
    results: list[dict],
    has_regression: bool,
    db_path: Optional[str] = None,
) -> int:
    """Persist a baseline-vs-candidate regression comparison."""
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO comparisons (suite_name, baseline_label, candidate_label, run_at, results, has_regression)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (suite_name, baseline_label, candidate_label, _now(), json.dumps(results), int(has_regression)),
        )
        return int(cursor.lastrowid)


def get_flakiness_report(suite_name: str, db_path: Optional[str] = None) -> list[dict[str, Any]]:
    """Compute per-test flakiness scores from historical pass-rate variance within a suite."""
    from .stats import flakiness_score as compute_flakiness

    with get_connection(db_path) as conn:
        test_names = [
            r["test_name"]
            for r in conn.execute(
                "SELECT DISTINCT test_name FROM runs WHERE suite_name = ?", (suite_name,)
            ).fetchall()
        ]

        report = []
        for test_name in test_names:
            rows = conn.execute(
                "SELECT pass_rate FROM runs WHERE suite_name = ? AND test_name = ? ORDER BY id",
                (suite_name, test_name),
            ).fetchall()
            pass_rates = [r["pass_rate"] for r in rows]
            latest = pass_rates[-1] if pass_rates else 0.0
            variance = (
                sum((r - sum(pass_rates) / len(pass_rates)) ** 2 for r in pass_rates) / len(pass_rates)
                if len(pass_rates) > 1
                else 0.0
            )
            report.append(
                {
                    "test_name": test_name,
                    "flakiness_score": compute_flakiness(pass_rates),
                    "current_pass_rate": latest,
                    "pass_rate_variance": variance,
                    "sample_size": len(pass_rates),
                }
            )
        return report


def save_test_result(suite_name: str, model: str, result: "TestResult", db_path: Optional[str] = None) -> int:
    """Persist a completed TestResult (summary + all iterations) and return the run id."""
    from .stats import flakiness_score as compute_flakiness

    history = get_history(suite_name, result.test_name, limit=20, db_path=db_path)
    past_rates = [h["pass_rate"] for h in history] + [result.pass_rate]

    run_id = save_run(
        suite_name=suite_name,
        test_name=result.test_name,
        model=model,
        total_iterations=result.total,
        passes=result.passes,
        pass_rate=result.pass_rate,
        threshold=result.threshold,
        meets_threshold=result.meets_threshold,
        avg_latency_ms=result.avg_latency_ms,
        ci_lower=result.ci_lower,
        ci_upper=result.ci_upper,
        flakiness=compute_flakiness(past_rates),
        db_path=db_path,
    )
    for i, run_result in enumerate(result.run_results):
        save_iteration(run_id, i, run_result, db_path=db_path)
    return run_id
