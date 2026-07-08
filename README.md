# Agenttest

**A testing framework for LLM agents and tool-calling.** Jest, but for agents that call tools non-deterministically.

## The problem

Every team building AI agents with tool-calling has the same blind spot: there's no reliable way to know whether an agent actually calls the right tools with the right arguments. You write a prompt, try it a few times in a playground, ship it, and hope. When someone tweaks the system prompt six weeks later, nothing tells you whether reliability just dropped from 95% to 70% — until a customer notices.

Existing test frameworks assume determinism: run the code, compare to an expected value, pass or fail. LLMs don't work that way. The same prompt can produce a correct tool call 19 times out of 20 and a subtly wrong one on the 20th. That's not a bug to fix — it's a distribution to measure. Agenttest treats LLM agent reliability as a statistics problem: it runs a test N times, computes a Wilson confidence interval on the pass rate, and uses Fisher's Exact Test to tell you whether a prompt or model change caused a *statistically significant* regression — not just "it failed one more time than before."

## Quick start

```bash
git clone <this-repo> && cd agenttest

# 1. Backend
cd backend
pip install -r requirements.txt
cp ../.env.example ../.env   # paste your GROQ_API_KEY in here
python main.py &

# 2. CLI — run the example suite
cd ..
python backend/cli/main.py run tests/examples/booking.yaml
```

That's five commands from zero to your first test run. Groq has a free tier — get a key at [console.groq.com](https://console.groq.com).

To use the dashboard instead of the CLI:

```bash
cd frontend
npm install
npm run dev
# open http://localhost:5173
```

<!-- screenshot: run-view -->
<!-- screenshot: history -->
<!-- screenshot: compare -->

## Writing a test suite

```yaml
version: "1.0"
suite: "Flight Booking Agent"
system_prompt: "You are a travel booking assistant. Use tools to help users."
model: "llama-3.3-70b-versatile"

tools:
  - name: search_flights
    description: "Search available flights"
    parameters:
      destination: {type: string, description: "City name"}
      date: {type: string, description: "YYYY-MM-DD format"}
    required: [destination, date]

  - name: book_flight
    description: "Book a specific flight"
    parameters:
      flight_id: {type: string}
    required: [flight_id]

tests:
  - name: "search before booking"
    message: "Book me the cheapest flight to Paris on July 15"
    runs: 20
    pass_threshold: 0.85

    assert_calls:
      - function: search_flights
        args:
          destination: {equals: "Paris"}
      - function: book_flight
        after: search_flights

    assert_order: [search_flights, book_flight]
```

Run it 20 times, and agenttest tells you the pass rate, the 95% confidence interval, and whether it clears your threshold — not just "1 of 20 failed." Full field reference: [docs/yaml-reference.md](docs/yaml-reference.md).

## Why this exists

- **Reliability is a distribution, not a boolean.** Every test runs N times; every result comes with a Wilson confidence interval, computed from scratch (no scipy).
- **Regressions need a statistical test, not a vibe check.** `agenttest compare` runs a baseline and a candidate prompt/model side by side and uses Fisher's Exact Test to flag genuine regressions and ignore noise.
- **Assertions are structural, not string-matching.** `assert_calls`, `assert_order`, `assert_no_calls`, and per-argument checks (`equals`, `type`, `contains`, `matches`, `not_null`) validate the actual shape of what the agent did.
- **Everything is inspectable.** A live dashboard streams every iteration over a WebSocket as it happens; a semantic diff engine shows exactly which arguments drifted between expected and actual tool calls.

## Architecture

```
┌─────────────┐       ┌──────────────────┐       ┌───────────────────┐
│  YAML suite │──────▶│   core/parser.py │──────▶│    core/runner.py  │
│ (your tests)│       │  (typed dataclasses)     │ (async, N parallel)│
└─────────────┘       └──────────────────┘       └─────────┬──────────┘
                                                             │
                        ┌────────────────────────────────────┼─────────────────────┐
                        ▼                                    ▼                     ▼
                ┌───────────────┐                  ┌──────────────────┐   ┌────────────────┐
                │ adapters/*.py │                  │ core/assertions  │   │  core/stats.py │
                │ (raw HTTP:    │                  │  .py (pass/fail  │   │ (Wilson CI,    │
                │ Groq/Claude/  │                  │  per iteration)  │   │  Fisher's test,│
                │ OpenAI/Ollama)│                  │                  │   │  flakiness)    │
                └───────────────┘                  └──────────────────┘   └────────────────┘
                                                             │
                                                             ▼
                                                   ┌───────────────────┐
                                                   │  core/storage.py  │
                                                   │  (SQLite, raw SQL)│
                                                   └─────────┬──────────┘
                                                             │
                        ┌────────────────────────────────────┼─────────────────────┐
                        ▼                                                          ▼
              ┌───────────────────┐                                     ┌──────────────────┐
              │  FastAPI + WS API │◀───────────────────────────────────▶│  React dashboard │
              │  (backend/api/)   │        REST + live WebSocket        │ (raw SVG charts) │
              └───────────────────┘                                     └──────────────────┘
```

## CLI reference

```
agenttest run <file>                                   Run a suite; exit 1 on any failed test (CI-friendly)
agenttest compare --baseline X --candidate Y --suite F  Regression comparison with p-values
agenttest benchmark --suite F --models a,b,c            Compare models on the same suite
agenttest serve                                         Start the API + dashboard
agenttest init                                          Scaffold a starter agenttest.yaml
agenttest report <run_id>                                Detailed report for a past run
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT
