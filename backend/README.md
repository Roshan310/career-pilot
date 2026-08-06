# Backend

FastAPI backend for the resume matcher + mock interview platform. It serves JSON only — the UI lives in
`../frontend/` and talks to it over HTTP, so every endpoint here is equally exercisable with curl/Postman
or the automated test suite. Billing/Stripe is deferred; usage limits use hardcoded free-tier caps. LLM
calls and embeddings use Google Gemini (not Anthropic/OpenAI as originally drafted in `docs/SPECS.md` —
see `docs/decisions.md` for context).

This directory is fully self-contained: its own `Dockerfile`, `pyproject.toml`, and `.env`. It doesn't
depend on anything outside `backend/` — `docker-compose.yml` at the repo root is what wires it together
with `frontend/` and the shared infra (Postgres/Redis/MinIO).

## Prerequisites

- Docker + Docker Compose
- **A Gemini API key** ([ai.google.dev](https://ai.google.dev/gemini-api/docs/api-key)) — required. It
  powers both text generation and embeddings; without it, resume and job creation fail outright.
- **A second Gemini API key** (`GEMINI_API_KEY_2`, from a different Google account) — optional but
  recommended for development. The free tier meters `generate_content` per project at 5 requests/minute
  plus a daily cap, which is easy to exhaust; a second account is a second quota pool, and
  `call_json()`, `call_transcription()` and `embed_text()` all fall over to it on a 429. With only the
  first key set everything behaves exactly as it did before the second existed.
- **An ElevenLabs API key** (`ELEVEN_LABS_API_KEY`) — optional. It gives the interviewer a natural
  voice; without it the audio endpoint returns 503 and the browser falls back to its own speech
  synthesis, which is worse and, in Brave or on Linux without `speech-dispatcher`, silent. The voice ID
  must be a **premade** voice — free accounts get `402 paid_plan_required` for library voices, and the
  error names the plan rather than the voice, so it reads like a bad key.

## First-time setup

Run from the **repo root** (docker-compose.yml lives there):

```bash
cp backend/.env.example backend/.env
# edit backend/.env and set GEMINI_API_KEY

docker compose up -d --build

# create the test database (isolated from dev data — see app/tests/conftest.py)
docker exec jaagir-sathi-postgres-1 psql -U jaagir -d jaagir_sathi -c "CREATE DATABASE jaagir_sathi_test"
docker exec jaagir-sathi-postgres-1 psql -U jaagir -d jaagir_sathi_test -c "CREATE EXTENSION IF NOT EXISTS vector"
```

One command brings up everything — Postgres, Redis, MinIO, the API, the RQ worker, and the frontend. The
`api` container runs `alembic upgrade head` on startup, so there's no separate migration step (you only
need `docker compose exec api alembic upgrade head` after writing a *new* migration).

After that, plain `docker compose up -d` is enough day to day; add `--build` only when dependencies or a
Dockerfile change, since the source is bind-mounted and `--reload` is on.

Note: Postgres is exposed on host port **5433** (not 5432) — this avoids clashing with a pre-existing
system-wide Postgres install. Containers still reach it at `postgres:5432` internally.

`curl localhost:8000/health` should return `{"status":"ok"}` once `api` is up.

## Running tests

```bash
docker compose exec api pytest app/tests/ -v
```

Tests run against the separate `jaagir_sathi_test` database and never touch dev data. LLM/embedding calls
are mocked at the module boundary in tests, so the suite runs without a real `GEMINI_API_KEY`.

Because the mocks return well-formed output, they can't catch a real model returning something the code
didn't anticipate — that has bitten this project once (see `AGENT.md` gotcha #6). Run one real session
end to end after changing anything that consumes LLM output.

## Project layout

`app/` — routers in `api/v1/`, business logic in `services/`, the one background job (matching) in
`workers/`, SQLAlchemy models in `models/`. See `../docs/architecture.md` for the full map.

## Known limitations

- No billing/Stripe — usage limits are enforced with hardcoded free-tier caps.
- Interview `mode` only fully supports `jd_specific`; `behavioral`/`technical` are accepted but route
  through the same generator with the gap-analysis section omitted.
- Voice is server-side: ElevenLabs speaks the questions (`GET /api/interviews/:id/turns/:n/audio`,
  cached in MinIO) and Gemini transcribes the answers (`POST /api/interviews/:id/transcribe`). The
  browser records audio and does voice-activity detection; it does no speech recognition, because the
  Web Speech API cannot be relied on (Brave returns a `network` error rather than results — see
  `../docs/decisions.md`, "Voice moved server-side"). Transcription is batch, not streaming, so there is
  no live word-by-word transcript; the streaming-STT WebSocket transport the seam was built for is still
  unbuilt.
- `POST /api/interviews` blocks 5-15s on question generation; the client is expected to show a loading
  state rather than poll (see `../docs/decisions.md`).
