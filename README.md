# DR. PROMPT

DR. PROMPT is a competitive platform for learning how to control AI systems by solving practical tasks through prompting: **Understand Task → Write Prompt → Run AI → Inspect Result → Submit → Evaluate → Improve**. Players write the instructions, see what the AI produced, and are scored by hidden evaluation.

This repository contains the modular-monolith product foundation: Supabase authentication, PostgreSQL persistence, versioned text challenges with visible Run and hidden Submit, deterministic graders, scoring, stars, XP, progression, leaderboards, profiles, an admin challenge builder, and five CONTROL foundation challenges.

Text-output challenges are the first challenge family, not the whole product. Application Challenge Platform v1 is implemented with **Responsive Hero** and **Pricing Grid**, plus APPLICATION authoring in the Admin Builder. The player's prompt drives an AI coding agent that edits a disposable copy of a small static app, which is then built, checked in a headless browser, and shown back to the player as screenshots. Image-prompt challenges are a later phase. See [`docs/CHALLENGE_TYPES.md`](docs/CHALLENGE_TYPES.md) for the direction, roadmap, and deferred decisions.

## Architecture

The repository contains two independently runnable applications:

- `frontend/`: Next.js App Router, strict TypeScript, Tailwind CSS, and shadcn/ui-compatible conventions.
- `backend/`: FastAPI with layered domain, application, port, and infrastructure boundaries.

The browser communicates only with the versioned backend API. Hidden tests and provider secrets must remain on trusted server infrastructure. See [`docs/`](docs/) for the durable architecture and security decisions.

## Prerequisites

- Node.js 22 or newer and npm
- `uv` (it installs and manages the required Python version and virtual environment)
- PostgreSQL 15 or newer for migrations, development seeding, and runtime challenge access
- For the APPLICATION challenge: Node.js on the backend's PATH and a Chromium for Playwright. Either run `uv run playwright install chromium`, or set `APPLICATION_BROWSER_CHANNEL=chrome` (or `msedge`) to use an installed browser.
- APPLICATION player execution defaults to a 10-second Run cooldown, 20-second Submit cooldown, and 180-second stale idempotency-reservation window. Override these with `APPLICATION_RUN_COOLDOWN_SECONDS`, `APPLICATION_SUBMIT_COOLDOWN_SECONDS`, and `APPLICATION_EXECUTION_LOCK_TIMEOUT_SECONDS`; coordination uses the configured PostgreSQL database and needs no Redis or worker.

## Environment setup

Copy the examples before starting either app:

```powershell
Copy-Item frontend/.env.example frontend/.env.local
Copy-Item backend/.env.example backend/.env
```

The defaults connect the local frontend to `http://localhost:8000`. Configure:

- Backend: `GROQ_API_KEY`, async `DATABASE_URL`, `ADMIN_API_KEY`, and the public `SUPABASE_URL` used to derive the JWT issuer/JWKS endpoint.
- Frontend browser: `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`.
- Frontend server only: `BACKEND_API_BASE_URL` and the same private `ADMIN_API_KEY` used by FastAPI.

The backend uses Supabase-hosted PostgreSQL without a Supabase SDK and does not require a service-role key. Normal automated tests require no live Groq, PostgreSQL, or Supabase project. Never put `DATABASE_URL`, `GROQ_API_KEY`, a Supabase secret/service-role key, or other backend credentials in `NEXT_PUBLIC_*` variables.

## Supabase dashboard setup

Repository configuration cannot enable hosted authentication providers. In the Supabase dashboard:

1. Use or migrate to asymmetric JWT signing keys so the project exposes public JWKS.
2. Set the Auth Site URL to `http://localhost:3000` and allow `http://localhost:3000/auth/callback` as a redirect URL.
3. Enable Google under Auth providers and enter its client ID and secret. In Google Cloud, use Supabase's provider callback URL: `https://<project-ref>.supabase.co/auth/v1/callback`.
4. Keep the Email provider enabled with email/password sign-in and email confirmation. Supabase's built-in email service is suitable only for limited development testing; configure custom SMTP before production.
5. Copy the project URL and publishable key into the frontend environment; copy only the project URL into the backend environment.

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

The explicit idempotent seed installs the five ordered CONTROL challenges and their versioned visible and hidden tests, plus Responsive Hero at level 6 and Pricing Grid at level 7. It never runs during application startup and does not remove submissions, user progress, or XP.

Open `http://localhost:3000`. The API health endpoint is available at `http://localhost:8000/api/v1/health`.

The challenge builder is at `http://localhost:3000/admin/challenges`. Enter the configured admin key once; Next.js validates it server-side and stores only an HttpOnly session proof. Browser JavaScript calls the same-origin BFF, which attaches the real key to FastAPI server-to-server. Draft saves never publish automatically. Choose TEXT or APPLICATION when creating a challenge. APPLICATION uses registered static packages and private/visible check presets; save drafts before testing. Run `alembic upgrade head` before starting this version. See [Application Platform v1](docs/APPLICATION_PLATFORM.md) for package policy, authoring, and migration details.

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

### Opt-in real Groq application smoke

Normal tests never contact Groq. To exercise the Responsive Hero coding agent against the
configured real provider, opt in explicitly from `backend/`:

```powershell
$env:RUN_REAL_GROQ_TESTS = "1"
$env:APPLICATION_BROWSER_CHANNEL = "chrome"
uv run python -m app.tools.smoke_application_agent --run-visible explicit
```

The command runs the four predefined prompt-quality cases by default. `--run-visible explicit`
sends the explicit case through the same disposable workspace, build, browser checks, and
screenshot path as application Run; the other cases stop after structured-output and edit
validation. Use one or more `--prompt explicit|concise|underspecified|awkward` options to limit
calls. `--plain-json` is a development comparison mode for the previous prompt-only JSON
contract. The report contains latency, format/edit validation, file count, build/check status,
screenshot count, safe failure category, and token usage when Groq provides it—never credentials,
raw responses, source contents, or hidden checks. The command creates no submission or XP.

If bundled Playwright Chromium has a version mismatch, keep
`APPLICATION_BROWSER_CHANNEL=chrome` to use installed Chrome. A missing browser or Node.js is an
infrastructure failure, not a failed player attempt.

## Repository structure

```text
frontend/   Next.js user interface and backend API client
backend/    FastAPI transport, domain/application code, PostgreSQL adapters, and migrations
docs/       Product, challenge types/roadmap, architecture, engineering, API, evaluation, security, and database notes
```

Before changing the repository, read [`docs/ENGINEERING_PRINCIPLES.md`](docs/ENGINEERING_PRINCIPLES.md) and the relevant domain documentation.
