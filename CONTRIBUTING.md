# Contributing to Agenttest

Thanks for considering a contribution. Agenttest is deliberately built with a minimal
dependency footprint — the statistics engine, assertion engine, and diff engine are all
pure Python with no scipy/numpy, and the frontend has no chart or component libraries.
Please keep that constraint in mind for PRs touching those areas.

## Development setup

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s ../tests/unit -p "test_*.py"
python -m unittest discover -s ../tests/integration -p "test_*.py"

# Frontend
cd frontend
npm install
npm run type-check
npm run lint
npm run dev
```

## Project layout

- `backend/core/` — the engine: parser, runner, assertions, stats, diff, storage, adapters. No FastAPI imports here — this package should work as a standalone library.
- `backend/api/` — FastAPI routes and the WebSocket handler. Thin wrappers around `core/`.
- `backend/cli/` — the command-line interface. Also a thin wrapper around `core/`.
- `frontend/src/` — React dashboard. Charts are raw SVG (see `components/LineChart.tsx` and `components/BarChart.tsx`) — no chart libraries.
- `tests/unit/` — fast, dependency-free unit tests for the four core engines.
- `tests/integration/` — runner tests against a fake adapter (no real network calls).

## Making changes

1. Fork and branch from `main`.
2. Write tests first where practical — `tests/unit/` is fast (`unittest`, no network).
3. Run the full check before opening a PR:
   ```bash
   python -m unittest discover -s tests/unit -p "test_*.py"
   python -m unittest discover -s tests/integration -p "test_*.py"
   cd frontend && npm run type-check && npm run lint && npm run build
   ```
4. Keep commits semantic: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`.
5. Open a PR against `main`. CI runs backend tests, frontend type-check/lint/build, and a Docker build.

## Adding a new LLM adapter

Implement `core/adapters/base.py`'s `LLMAdapter` interface with raw `httpx` calls — no
provider SDKs. Register it in `core/adapters/__init__.py`'s `get_adapter()` model-name
dispatch. See `core/adapters/groq.py` for the simplest reference implementation.

## Reporting bugs

Open an issue with your suite YAML (redact anything sensitive), the command you ran, and
the output. If it's a statistics question (why did this pass/fail?), include the raw
pass/total counts — `core/stats.py` is deterministic and easy to reason about from those alone.
