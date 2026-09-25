# DR. PROMPT

DR. PROMPT is a web-based prompt-engineering skill game built around the loop **Write → Run → Submit → Diagnose → Improve**. This repository is the modular-monolith foundation for the product; gameplay, evaluation, accounts, and persistence are intentionally deferred.

## Architecture

The repository contains two independently runnable applications:

- `frontend/`: Next.js App Router, strict TypeScript, Tailwind CSS, and shadcn/ui-compatible conventions.
- `backend/`: FastAPI with layered domain, application, port, and infrastructure boundaries.

The browser communicates only with the versioned backend API. Hidden tests and provider secrets must remain on trusted server infrastructure. See [`docs/`](docs/) for the durable architecture and security decisions.

## Prerequisites

- Node.js 22 or newer and npm
- `uv` (it installs and manages the required Python version and virtual environment)

## Environment setup

Copy the examples before starting either app:

```powershell
Copy-Item frontend/.env.example frontend/.env.local
Copy-Item backend/.env.example backend/.env
```

The defaults connect the local frontend to `http://localhost:8000`. Set `GROQ_API_KEY` in `backend/.env` only when manually constructing the Groq provider; normal startup and automated tests do not require it. `GROQ_TIMEOUT_SECONDS` defaults to 30 seconds. Supabase placeholders remain unused. Never put backend secrets in `NEXT_PUBLIC_*` variables.

## Install and run

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

Backend (from `backend/`):

```powershell
uv sync --dev
uv run fastapi dev app/main.py
```

Open `http://localhost:3000`. The API health endpoint is available at `http://localhost:8000/api/v1/health`.

## Quality checks

Frontend (from `frontend/`):

```powershell
npm run lint
npm run typecheck
npm run test
npm run build
```

Backend (from `backend/`):

```powershell
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run python -c "from app.main import app; print(app.title)"
```

## Repository structure

```text
frontend/   Next.js user interface and backend API client
backend/    FastAPI transport, application/domain code, ports, and adapters
docs/       Product, architecture, engineering, API, evaluation, and security notes
```

Before changing the repository, read [`docs/ENGINEERING_PRINCIPLES.md`](docs/ENGINEERING_PRINCIPLES.md) and the relevant domain documentation.
