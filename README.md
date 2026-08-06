<div align="center">

# Jaagir Sathi

## Your dream tech job is waiting for you! Go, grab it!
</div>

AI-powered resume matcher + mock interview platform. Two independent, self-contained projects live side
by side in this repo:

- **`backend/`** — FastAPI API (auth, resume/JD parsing, matching, mock interview). See
  `backend/README.md`. No billing.
- **`frontend/`** — Next.js 14 app router UI, including the live voice interview. See `AGENT.md` for the
  conventions. Voice is server-side (ElevenLabs speaks the questions, Gemini transcribes the answers), so
  the interview works in any browser with a microphone; browsers without one fall back to typing.

`docker-compose.yml` at this root level is the only thing that spans both — it orchestrates `backend/`,
`frontend/`, and shared infra (Postgres/Redis/MinIO) as sibling services, each built from its own
subdirectory.

```bash
cp backend/.env.example backend/.env   # then set GEMINI_API_KEY
docker compose up -d                   # API on :8000, UI on :3000
```

For anyone (human or agent) picking this project up: read `docs/project_overview.md` first, then
`docs/architecture.md`, then `docs/decisions.md` — or just `AGENT.md`, which points to all three.

To stop the running containers
```bash
docker compose stop 
```