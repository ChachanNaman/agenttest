# API Reference

All REST endpoints are prefixed with `/api`. The server also exposes one WebSocket endpoint at `/ws/run`.

## REST endpoints

### `POST /api/run`

Run every test in a suite file synchronously and persist the results.

**Request body:**
```json
{ "suite_file": "tests/examples/booking.yaml" }
```

**Response:**
```json
{
  "run_id": 1,
  "suite": "Flight Booking Agent",
  "results": [
    {
      "test_name": "search before booking",
      "passes": 17,
      "total": 20,
      "pass_rate": 0.85,
      "meets_threshold": true,
      "verdict": "PASS — 85.0% (CI: 64–95%) vs threshold 85%",
      "ci_lower": 0.64,
      "ci_upper": 0.95,
      "avg_latency_ms": 1240.5,
      "failures": [{ "iteration": 3, "reasons": ["..."] }]
    }
  ]
}
```

### `GET /api/runs?suite=<name>`

List all persisted run summaries, optionally filtered by suite name. Returns most recent first.

### `GET /api/runs/{run_id}`

Fetch one run's summary plus every iteration recorded for it. 404 if not found.

### `GET /api/history/{suite_name}/{test_name}?limit=50`

Time-ordered run history for one test — the data source for the History page's charts.

### `GET /api/flakiness/{suite_name}`

Flakiness scores (0.0–1.0) for every test with run history in the suite, computed from the variance of historical pass rates.

### `POST /api/compare`

Run a suite under two configurations (baseline/candidate) and report per-test regressions using Fisher's Exact Test.

**Request body:**
```json
{
  "suite_file": "tests/examples/booking.yaml",
  "runs": 30,
  "baseline": { "label": "v1", "system_prompt": "...", "model": "..." },
  "candidate": { "label": "v2", "system_prompt": "...", "model": "..." }
}
```
`system_prompt` and `model` are optional per variant — omit to use the suite's defaults.

**Response:**
```json
{
  "suite": "Flight Booking Agent",
  "baseline_label": "v1",
  "candidate_label": "v2",
  "has_regression": true,
  "results": [
    {
      "test_name": "handles vague date",
      "baseline_pass_rate": 0.88,
      "candidate_pass_rate": 0.71,
      "delta": -0.17,
      "p_value": 0.003,
      "is_regression": true,
      "verdict": "REGRESSION — pass rate dropped 17.0pp (p=0.003, statistically significant)"
    }
  ]
}
```

### `POST /api/benchmark`

Run the same suite once per model.

**Request body:**
```json
{ "suite_file": "tests/examples/booking.yaml", "models": ["llama-3.3-70b-versatile", "claude-haiku-4-5"], "runs": 20 }
```

**Response:**
```json
{
  "suite": "Flight Booking Agent",
  "models": [
    { "model": "llama-3.3-70b-versatile", "pass_rate": 0.91, "avg_latency_ms": 980.2, "tests": [...] }
  ]
}
```

### `GET /api/snapshots/{suite_name}/{test_name}?function_name=search_flights`

Fetch the most recently saved argument-schema snapshot for a function.

### `POST /api/snapshots/{suite_name}/{test_name}`

Save a new snapshot.

```json
{ "function_name": "search_flights", "arg_schema": { "destination": "string", "date": "string" } }
```

### `GET /api/health`

Liveness check: `{"status": "ok"}`. Used by the dashboard's connection indicator.

## WebSocket: `/ws/run`

Connect, then send one JSON message to start a run:

```json
{ "suite_file": "tests/examples/booking.yaml" }
```

The server streams one JSON event per line for the duration of the run, then closes the socket.

| `type` | Fields | When |
|---|---|---|
| `run_started` | `suite`, `total_tests` | Once, immediately after the suite parses. |
| `test_started` | `test_name`, `runs` | Once per test, before its iterations begin. |
| `iteration_complete` | `test_name`, `iteration`, `passed`, `current_pass_rate` | After every iteration of every test. |
| `test_complete` | `test_name`, `pass_rate`, `meets_threshold`, `verdict` | Once per test, after all its iterations finish. |
| `run_complete` | `passed`, `failed`, `total` | Once, after every test in the suite finishes. |
| `error` | `message` | On a parse failure or unhandled exception; the socket closes immediately after. |

The socket is always closed by the server once the run (or an error) completes — clients should treat socket closure as the definitive "done" signal rather than only `run_complete`.
