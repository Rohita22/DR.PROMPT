# Challenge Types

DR. PROMPT supports two executable challenge families: TEXT and APPLICATION. IMAGE is reserved but unsupported. Shared authentication, progression, scoring, stars, XP, per-challenge leaderboards, profiles, and immutable versioning apply across executable families.

## TEXT — implemented

Five CONTROL foundations evaluate model output with deterministic graders. Visible Run and hidden Submit retain their original contracts and all 40 golden regression comparisons. Text content remains part of the learning path.

## Application Platform v1 — implemented

The player instructs a coding agent to modify a disposable static HTML/CSS starter. Repository packages, typed configuration, a trusted check registry, browser measurements, screenshots, and APPLICATION Admin Builder support are implemented. **Responsive Hero** is CONTROL 6; **Pricing Grid** is CONTROL 7. One executor handles both. See [APPLICATION_PLATFORM.md](APPLICATION_PLATFORM.md) for the package representation, ownership rules, per-challenge checks, migration, authoring, and safety boundary.

The agent may replace only package-declared HTML/CSS files. JavaScript is disabled in the evaluator and executable files are protected. Admin selects registered packages and check presets; admin cannot upload code or turn strings into commands. Hidden check detail remains restricted to admin tools.

## Application prototype — historical milestone

Responsive Hero proved the single-shot coding-agent path. Strict Groq Structured Outputs and low reasoning were validated on 2026-10-01; all four prompt-quality cases parsed successfully, and one full real-provider Run passed its four visible checks with two screenshots. This is a small development smoke sample, not a model-quality guarantee. Platform v1 retains the agent protocol and Hero's existing version/history while replacing its one-off browser/check infrastructure.

## Isolation and deferred decisions

The local disposable workspace is process-level isolation, not an OS sandbox. It has fixed commands, a minimal child environment, timeouts, path confinement, no page scripts, and file-only browser requests. It has no OS-enforced CPU, memory, or process quotas. A deliberately designed real sandbox is required before JavaScript, Python, shell, server, or build-script editing challenges are allowed.

Deferred: executable-code sandbox technology, multi-step agents, durable artifact storage, live previews, dedicated applied tracks, weighted application checks, third application content, user-uploaded packages, and an image challenge prototype. Player application runs already use cooldowns/advisory locking and durable Submit idempotency; queues remain out of scope.

## IMAGE — deferred

A future image family needs explicit decisions about models, seeds, visual comparison, cost, nondeterminism, and artifact retention. No IMAGE editor, executor, or publish path is implemented.
