# Getting Started

This walks through installation, running the bundled example suite, and writing your first test — start to finish.

## 1. Get a Groq API key (free)

Agenttest needs a live LLM to call. Groq has a generous free tier and the fastest inference of any supported provider, so it's the default.

1. Go to [console.groq.com](https://console.groq.com) and sign up.
2. Click **API Keys** → **Create API Key**.
3. Copy the key.

## 2. Install

```bash
git clone <this-repo>
cd agenttest
cp .env.example .env
```

Paste your key into `.env`:

```
GROQ_API_KEY=gsk_...
```

Install the backend:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## 3. Run the example suite

From the repo root:

```bash
python backend/cli/main.py run tests/examples/booking.yaml
```

You'll see output like:

```
🧪 Agenttest v1.0.0
Running suite: Flight Booking Agent
Model: llama-3.3-70b-versatile

  ▸ search before booking (20 runs)...
    ✓ PASS — 85.0% (CI: 64–95%) | 1,240ms avg

  ▸ handles vague date (15 runs)...
    ✗ FAIL — 67.0% (CI: 41–86%) | 1,180ms avg
      Reason: search_flights called with null date in 5/15 runs

──────────────────────────────────
Results: 1/2 tests passed
Exit code: 1 (failure)
```

The exit code is 0 only if every test clears its `pass_threshold` — wire this straight into CI.

## 4. Explore the dashboard (optional)

```bash
# Terminal 1
cd backend && python main.py

# Terminal 2
cd frontend && npm install && npm run dev
```

Open `http://localhost:5173`. Type `tests/examples/booking.yaml` into the Run page and click **Run suite** — you'll see each iteration stream in live over a WebSocket.

## 5. Write your own suite

Run `agenttest init` in an empty directory to scaffold a starter file:

```bash
python backend/cli/main.py init
```

This creates `agenttest.yaml` with one tool and one test. Edit it to describe your agent's actual tools and expected behavior, then:

```bash
python backend/cli/main.py run agenttest.yaml
```

For the full YAML syntax (all assertion types, multi-turn conversations, thresholds), see [yaml-reference.md](yaml-reference.md).

## 6. Catch regressions before they ship

Once you have a baseline suite passing, compare it against a prompt change before merging:

```bash
python backend/cli/main.py compare \
  --suite tests/examples/booking.yaml \
  --baseline "You are a travel booking assistant." \
  --candidate "You are a friendly, proactive travel booking assistant who upsells." \
  --runs 30
```

Agenttest runs both prompts N times each and reports a p-value per test — a change is only flagged as a **regression** if the drop is statistically significant, not just numerically different.
