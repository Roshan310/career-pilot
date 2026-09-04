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

## About the project

Jaagir Sathi helps job seekers compare a resume with a specific job description and practice an
interview tailored to that pairing. It combines structured resume and job parsing, vector similarity,
rule-based scoring, and AI-generated feedback in one workflow.

A typical user journey is:

1. Create an account and upload a PDF, DOCX, or TXT resume.
2. Add a job description.
3. Start a match analysis and wait for the background worker to calculate the result.
4. Review the overall score, skill gaps, and resume improvement suggestions.
5. Start a mock interview generated from the resume, job description, and identified gaps.
6. Complete the interview and review question-level feedback, overall findings, and speech metrics.

The project currently includes authentication, resume and job management, asynchronous match analysis,
usage limits, mock interviews, interview history, and reports. Billing is not implemented.

## Technology stack

| Area | Technology |
|---|---|
| Frontend | Next.js 14, React 18, TypeScript, Tailwind CSS, TanStack Query |
| API | FastAPI, Python 3.12, Pydantic |
| Database | PostgreSQL 16 with pgvector, SQLAlchemy, Alembic |
| Background jobs | Redis and RQ |
| File and audio storage | MinIO, using the S3 API |
| AI and embeddings | Google Gemini |
| Interview voice | ElevenLabs, with browser speech synthesis as a fallback |
| Authentication | JWT access and refresh tokens |
| Tests | pytest, pytest-asyncio, and HTTPX |

## Repository structure

```text
.
├── backend/                 FastAPI application, migrations, worker, and tests
│   ├── alembic/             Database migrations
│   └── app/
│       ├── api/v1/          HTTP routes
│       ├── models/          SQLAlchemy models
│       ├── schemas/         Request and response schemas
│       ├── services/        Business logic and external service integrations
│       ├── tests/           Backend test suite
│       └── workers/         RQ queue and matching job
├── frontend/                Next.js application
│   ├── app/                 Routes and layouts
│   ├── components/          UI and feature components
│   ├── hooks/               React Query and interview hooks
│   └── lib/                 API client, types, utilities, and voice providers
├── docs/                    Project overview, architecture, decisions, and specification
├── docker-compose.yml       Local development stack
└── docker-compose.prod.yml  Production-oriented Compose configuration
```

The backend and frontend are self-contained projects. They communicate through the JSON API and do not
import code from each other. The root Compose file connects both applications to the shared services.

## Prerequisites

For the recommended setup, install:

- Docker Engine or Docker Desktop
- Docker Compose v2, available through the `docker compose` command
- Git
- A Google Gemini API key

An ElevenLabs API key is optional. It enables server-generated interviewer audio and ElevenLabs Scribe
transcription. Without it, transcription falls back to Gemini and question audio falls back to browser
speech synthesis when supported.

If you want to run the frontend directly on the host, also install Node.js 22 and npm.

## Local setup

### 1. Configure the backend

From the repository root, create the local environment file:

```bash
cp backend/.env.example backend/.env
```

Open `backend/.env` and set at least these values:

```dotenv
GEMINI_API_KEY=your-gemini-api-key
JWT_SECRET_KEY=replace-this-with-a-long-random-value
```

The checked-in example already contains the local PostgreSQL, Redis, MinIO, model, CORS, usage limit,
and interview settings. `GEMINI_API_KEY_2` can optionally hold a key from a second Google project for
quota failover. `ELEVEN_LABS_API_KEY` is optional.

Do not commit `backend/.env` or real API keys.

### 2. Build and start the stack

```bash
docker compose up -d --build
```

The first build can take several minutes. Compose waits for the infrastructure health checks before
starting the API. The API automatically applies all Alembic migrations during startup.

Check the container state and follow startup logs with:

```bash
docker compose ps
docker compose logs -f api worker frontend
```

Press `Ctrl+C` to stop following logs. The containers continue running in the background.

### 3. Verify the application

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/ready
```

The liveness endpoint should return `{"status":"ok"}`. The readiness endpoint also checks PostgreSQL
and Redis.

Open the following local URLs:

| Service | URL |
|---|---|
| Web application | http://localhost:3000 |
| API documentation | http://localhost:8000/docs |
| Alternative API documentation | http://localhost:8000/redoc |
| MinIO console | http://localhost:9001 |

The default local MinIO username and password are both `minioadmin`.

## Local service ports

| Service | Host port | Purpose |
|---|---:|---|
| Frontend | 3000 | Next.js development server |
| API | 8000 | FastAPI HTTP server |
| PostgreSQL | 5433 | Development database |
| Redis | 6379 | Queue and rate-limit storage |
| MinIO API | 9000 | S3-compatible object storage |
| MinIO console | 9001 | Storage administration UI |

PostgreSQL intentionally uses host port 5433. Inside the Compose network, the API and worker connect to
the database at `postgres:5432`.

## How the application works

The frontend sends authenticated requests to the FastAPI application under `/api`. Most operations run
inside the API request, including resume parsing, job parsing, interview generation, and answer
evaluation.

Match analysis is asynchronous. Creating a match stores a pending record and places a job on Redis. The
RQ worker calculates semantic similarity, skill overlap, experience alignment, keyword density, gaps,
and suggestions. The frontend polls the API until the match is complete or has failed.

Uploaded resumes and generated interview audio are stored in MinIO. PostgreSQL stores users, parsed
documents, matches, interview sessions, turns, and reports. Gemini provides structured text generation
and 1,536-dimensional embeddings.

## Common development commands

Run these commands from the repository root:

```bash
# Start existing containers
docker compose up -d

# Rebuild after changing dependencies or a Dockerfile
docker compose up -d --build

# View all service logs
docker compose logs -f

# View one service log
docker compose logs -f api

# Apply migrations manually
docker compose exec api alembic upgrade head

# Stop containers without deleting data
docker compose stop

# Stop and remove containers while retaining named volumes
docker compose down
```

Source directories are mounted into the development containers. Backend code reloads through Uvicorn,
and frontend code reloads through the Next.js development server. A rebuild is normally needed only
after a dependency or Dockerfile change. If `backend/.env` changes, recreate the affected containers
with `docker compose up -d api worker`; `docker compose restart` does not reload Compose environment
files.

## Running the frontend outside Docker

The frontend can run on the host while the backend and infrastructure remain in Docker:

```bash
docker compose up -d postgres redis minio api worker
docker compose stop frontend
cd frontend
npm ci
npm run dev
```

The API client uses `NEXT_PUBLIC_API_URL` when it is set and otherwise defaults to
`http://localhost:8000`. Do not run both frontend processes at once because they both use port 3000.





