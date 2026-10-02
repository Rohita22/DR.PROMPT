# Application Challenge Platform v1

Platform v1 runs static HTML/CSS tasks through one `ApplicationChallengeExecutor`. The two shipped packages are **Responsive Hero** (CONTROL 6) and **Pricing Grid** (CONTROL 7). IMAGE and executable-code challenges remain unsupported.

## Package representation and ownership

`backend/application_challenges/<registered_directory>/` contains `manifest.json`, the immutable `starter/`, and optional committed `preview/<viewport>.png` images. The explicit catalog in `StarterProjectRepository` maps opaque package IDs to directories; database or admin values are never interpreted as paths. Each published package ID is a stable version reference. Introduce a new registered package ID and challenge version when changing its execution semantics; do not replace published package assets in place.

The manifest contains display metadata, defaults, protected paths, and trusted check definitions. It owns the starter, HTML entry, fixed build argv (`node build.mjs`), output entry, maximum HTML/CSS edit universe, measurement dimensions, check implementation/parameter presets, public screenshot presets, and maximum execution limits. Source code, check implementations, and manifests never enter a coding agent's workspace; only `starter/` does.

`ApplicationChallengeConfig` is immutable and persisted in the existing `application_config` JSONB. Schema version **1** identifies the validated shape, including configured viewports and screenshot flags. The existing `starter_project` field is retained as the registered package reference. Structural build fields remain persisted for reproducibility but must match package policy exactly. Admin requests cannot set them.

Admin selects a package, a nonempty subset of allowed files, nonempty visible and hidden check subsets, safe screenshot views and their labels, and positive execution limits no greater than package maxima. Preset selectors, expected content, measurement dimensions, and tolerances are repository-owned in v1; selecting a preset selects its typed parameters. The builder shows viewport/count/width metadata, not evaluator JSON or a code editor. Configuration loaded from PostgreSQL is strictly parsed again and checked against package policy. Execution independently validates it before workspace creation or provider invocation.

## Runtime and checks

```text
versioned configuration → registered package + policy validation
  → ApplicationChallengeExecutor
  → disposable workspace → CodingAgent → independent edit validation
  → fixed build → JavaScript-disabled browser measurements
  → ApplicationCheckRegistry → normalized execution result
  → Run feedback or aggregate Submit → existing scoring/progression transaction
```

`ApplicationPackageLoader` is a domain port. `StarterProjectRepository` implements it and the existing preview reader. It rejects unknown IDs, traversal, symlinks/junctions, missing files, unknown check implementations, unsafe build configuration, and policy expansion. The registry is immutable per instance; tests cannot mutate shared global dispatch state.

The narrow `ApplicationCheckResult` carries ID, pass/fail, safe label, and diagnostic. Trusted implementations consume `ApplicationFacts`, selector-indexed `ElementMetrics`, and typed `CheckParameters`; they cannot execute administrator expressions. Available concepts are build success, horizontal row, vertical stack, visibility, clickability, overflow, required structure, preserved text, preserved link destinations, prominence, protected markup, and protected files. The browser only measures. Selector values are passed as arguments to fixed trusted measurement code; page JavaScript stays disabled.

Run evaluates selected visible checks. Submit evaluates selected hidden checks (which can repeat visible requirements), scores `passed / total × 100`, and returns aggregates plus the first configured safe screenshot. Hidden IDs, labels, diagnostics, expected content, measurement viewports, and selectors never appear in public detail or Submit. Admin Test makes **one** coding-agent call, evaluates the union of visible and hidden checks over that result, and shows both groups. Its preview score describes that union; authoritative Submit uses only the hidden suite. Admin Test has no gameplay write dependencies.

## Shipped content

Hero retains four Run checks and nine Submit checks. Its existing ID, version 1, order, model configuration, scoring, submissions, and progression remain compatible. Migration `0008_application_platform` only adds schema identification and the equivalent existing viewport policy to legacy Hero JSONB; it does not change evaluation, current-version pointers, or player history. No runtime branch selects a challenge by slug.

Pricing Grid uses the same loader, workspace, agent, build runner, browser, registry, and executor:

| Mode | Checks |
| --- | --- |
| Run (4) | Build; three desktop cards, each at least 20% viewport width; Pro has a distinct background or contrasting border at least 2px wide; no overflow at 390px |
| Submit (15) | Those four, plus original plan names, prices, all three clickable actions, stacked cards within phone width at 390px and 320px, unchanged header, unchanged footer, required pricing structure, unchanged protected files, no overflow at 320px, original features, original action destinations |

Prominence is deterministic; no LLM judge is involved. The untouched pricing layout is below the 70% completion threshold. Both use 70/85/100 evaluation star thresholds, a 150-token three-star ceiling, a 400-token hard prompt limit, and the existing 80/20 evaluation/efficiency weighting. Pricing Grid is not a boss. Normal first three-star completion awards 175 XP. One star on Hero unlocks Pricing Grid. Leaderboards remain per challenge/version/model; profile totals derive from published content.

## Admin and player experience

The existing builder offers TEXT or APPLICATION at creation. Type cannot change after creation, including when cloning a new version. Published versions remain immutable; create a draft version to alter policy. IMAGE requests are rejected. Application forms replace text test-case editors and preserve shared basics, instructions, model, scoring, test, and publication controls. Private checks are visibly marked. Test output includes visible/private checks, screenshots, sanitized build output, and changed-file counts, without XP or submissions.

Player briefs show challenge-specific instructions, starter reference, and allowed files. Screenshots render from artifact labels, IDs, and dimensions, without assuming a fixed pair. The existing Run/Submit state, provider errors, rejected edits, build failures, cooldown feedback, score, stars, XP, and leaderboard remain shared.

## Safety and limits

Only existing allowlisted `.html` and `.css` files may be replaced. No shell tools, dependency installation, uploaded project/evaluator code, or arbitrary commands exist. Build/browser child environments omit backend secrets. Workspaces are confined, checked for links, fresh per attempt, and cleaned after success or failure. Browser requests are restricted to local build output, JavaScript and service workers are disabled, and downloads are disabled. Hidden evaluators never enter the workspace or model input.

Player execution retains per-user advisory locking, 10-second Run and 20-second Submit cooldowns, and durable scoped Submit idempotency. Screenshot payload serialization preserves safe labels and remains compatible with older replay records without labels. TEXT contracts and golden results are unchanged.

This remains process-level isolation, **not an OS sandbox**. CPU/memory/process quotas, arbitrary executable code, interactive previews, durable result artifact storage, queues, uploaded/user-generated packages, and IMAGE are deferred. Screenshot data is inline and ephemeral. Model nondeterminism remains. Package dimensions and evaluator parameters require a reviewed repository change; v1 intentionally exposes preset selection rather than unrestricted evaluator authoring.

## Verification

From `backend/`, use `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run alembic heads`, and `uv run alembic upgrade head --sql`. Set `APPLICATION_BROWSER_CHANNEL=chrome` or `msedge` when using an installed Chromium browser. Pricing tests use fake agents with real builds/browser checks. PostgreSQL tests require `TEST_DATABASE_URL` pointing to a disposable database and use isolated schemas.

`python -m app.infrastructure.application.render_starter_preview pricing-grid` regenerates committed starter previews through the same safe evaluator. Canonical starter files are not modified by rendering or execution tests. Frontend checks remain `npm run lint`, `npm run typecheck`, `npm run test`, and `npm run build`.
