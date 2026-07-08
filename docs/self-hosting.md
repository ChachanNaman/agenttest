# Self-Hosting

Agenttest ships as a single Docker image containing the FastAPI backend and the built React
dashboard (served as static files from the same process).

## Docker Compose (recommended)

```bash
cp .env.example .env   # fill in GROQ_API_KEY at minimum
docker compose up --build
```

The dashboard and API are both available at `http://localhost:8000`. `docker-compose.yml`
mounts two host directories into the container:

- `./data` → `/app/data` — the SQLite database persists here across restarts.
- `./tests` → `/app/tests` — edit suite YAML files on the host; the container sees them immediately.

## Plain Docker

```bash
docker build -t agenttest .
docker run -p 8000:8000 \
  -e GROQ_API_KEY=gsk_... \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/tests:/app/tests \
  -e DATABASE_PATH=/app/data/agenttest.db \
  agenttest
```

## Without Docker

```bash
# Build the frontend once
cd frontend && npm install && npm run build && cd ..

# Copy the build into the backend's static directory
cp -r frontend/dist backend/static

# Run the backend — it serves both the API and the static dashboard
cd backend
pip install -r requirements.txt
python main.py
```

## Configuration

All configuration is environment variables (see `.env.example`):

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `GROQ_API_KEY` | for Groq models | — | Free tier at [console.groq.com](https://console.groq.com). |
| `ANTHROPIC_API_KEY` | for Claude models | — | |
| `OPENAI_API_KEY` | for GPT models | — | |
| `PORT` | no | `8000` | Backend listen port. |
| `DATABASE_PATH` | no | `./agenttest.db` | SQLite file location. |
| `CORS_ORIGINS` | no | `http://localhost:5173` | Comma-separated allowed origins. |

Ollama models need no API key — they call `http://localhost:11434` by default (override with `OLLAMA_BASE_URL`), so `ollama serve` must be reachable from wherever agenttest runs. In Docker, that means either running Ollama on the host and using `http://host.docker.internal:11434`, or running it as a sibling container on the same network.

## Releasing

`.github/workflows/release.yml` builds and pushes a versioned image to GitHub Container
Registry on every `v*` tag push, and drafts a GitHub release with auto-generated notes:

```bash
git tag v1.0.0
git push origin v1.0.0
```

Then pull it anywhere:

```bash
docker pull ghcr.io/<org>/<repo>:1.0.0
```
