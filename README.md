# DR. PROMPT

DR. PROMPT is a web-based prompt-engineering skill game built around the loop **Write → Run → Submit → Diagnose → Improve**. This repository contains the modular-monolith product foundation, deterministic evaluation, Supabase OAuth, scored submissions, and PostgreSQL persistence adapters.

## Architecture

The repository contains two independently runnable applications:

- `frontend/`: Next.js App Router, strict TypeScript, Tailwind CSS, and shadcn/ui-compatible conventions.
- `backend/`: FastAPI with layered domain, application, port, and infrastructure boundaries.

The browser communicates only with the versioned backend API. Hidden tests and provider secrets must remain on trusted server infrastructure. See [`docs/`](docs/) for the durable architecture and security decisions.

## Prerequisites

- Node.js 22 or newer and npm
- `uv` (it installs and manages the required Python version and virtual environment)
- PostgreSQL 15 or newer for migrations, development seeding, and runtime challenge access

## Environment setup

Copy the examples before starting either app:

```powershell
Copy-Item frontend/.env.example frontend/.env.local
Copy-Item backend/.env.example backend/.env
```

The defaults connect the local frontend to `http://localhost:8000`. Configure:

- Backend: `GROQ_API_KEY`, async `DATABASE_URL`, and the public `SUPABASE_URL` used to derive the JWT issuer/JWKS endpoint.
- Frontend: `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`.

The backend uses Supabase-hosted PostgreSQL without a Supabase SDK and does not require a service-role key. Normal automated tests require no live Groq, PostgreSQL, or Supabase project. Never put `DATABASE_URL`, `GROQ_API_KEY`, a Supabase secret/service-role key, or other backend credentials in `NEXT_PUBLIC_*` variables.

## Supabase dashboard setup

Repository configuration cannot enable third-party OAuth providers. In the Supabase dashboard:

1. Use or migrate to asymmetric JWT signing keys so the project exposes public JWKS.
2. Set the Auth Site URL to `http://localhost:3000` and allow `http://localhost:3000/auth/callback` as a redirect URL.
3. Enable Google and GitHub under Auth providers and enter each provider's client ID and secret.
4. In the Google/GitHub developer consoles, use Supabase's provider callback URL: `https://<project-ref>.supabase.co/auth/v1/callback`.
5. Copy the project URL and publishable key into the frontend environment; copy only the project URL into the backend environment.

Traditional password authentication is intentionally not configured.

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
uv run alembic upgrade head
uv run python -m app.infrastructure.database.seed
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
backend/    FastAPI transport, domain/application code, PostgreSQL adapters, and migrations
docs/       Product, architecture, engineering, API, evaluation, security, and database notes
```

Before changing the repository, read [`docs/ENGINEERING_PRINCIPLES.md`](docs/ENGINEERING_PRINCIPLES.md) and the relevant domain documentation.
