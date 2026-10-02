# Product

DR. PROMPT is a competitive platform for learning how to control AI systems by solving practical tasks through prompting.

**Learn to control AI by making it solve real tasks. Your instructions. The AI's result. Hidden evaluation.**

The product is designed for developers, technical learners, and prompt practitioners who learn best by observing what an AI did, diagnosing why it succeeded or failed, and refining their instructions. It should feel closer to a programming challenge platform and puzzle game than an online course.

## Product loop and hypothesis

The primary loop is:

**Understand Task → Write Prompt → Run AI → Inspect Result → Submit → Evaluate → Improve**

For applied challenges, the same loop becomes:

**Environment → Prompt → AI Action → Result Artifact → Evaluation → Improve**

The AI-produced result is part of the learning experience. A score alone is insufficient when the result can be shown safely. Players should be able to connect their wording to the generated text, modified application, image, test result, or other artifact and use that evidence for the next attempt.

The core hypothesis remains that players will voluntarily replay completed challenges to improve their score and produce a more reliable functional result. The next product experiment should test whether applied tasks create stronger diagnosis and retry behavior than text-only output constraints.

## Challenge families

DR. PROMPT is expected to support multiple challenge families. These families share the competitive product shell but use different execution environments and evaluation components.

### Text and prompt-control challenges — implemented

The current challenge family evaluates an LLM's text response to a player-authored prompt and test input. It covers exact output control, formatting restrictions, extraction, classification, structured output, and instruction following.

```text
player prompt + test input → LLM text output → deterministic grader
```

These challenges remain valuable for onboarding, fundamentals, regression coverage, and deterministic skill building. The five current CONTROL challenges are valid foundation/tutorial content and exercise the implemented product systems. They are not the final quality bar or the entire future catalog.

### Application and coding-agent challenges — Platform v1 implemented

The player receives a controlled starter application or repository plus an objective. The player does not edit the application directly; their prompt instructs an AI coding agent to modify or repair it.

Examples include fixing a broken form, implementing validation, repairing a filtering bug, making a page responsive, improving accessibility, or implementing a requested frontend behavior.

```text
starter application + player prompt
→ AI coding agent
→ modified application
→ build/tests/browser evaluation
→ inspectable result artifacts
→ normalized evaluation result
```

The player may inspect a rendered preview, screenshots, changed-file summary, build state, test outcomes, and safe diagnostics. Programmatic checks remain preferred over subjective LLM judging.

**Implemented:** **Responsive Hero** (level 6, after the CONTROL boss) and **Pricing Grid** (level 7). Both are static HTML/CSS tasks, with reusable repository packages and APPLICATION authoring in the existing builder. The player sees a small static landing page and its requirements, then writes a prompt for a coding agent. The agent edits a disposable copy through a constrained whole-file protocol. Run shows the starter and the AI's result side by side (desktop and phone screenshots), visible checks, the build, and changed files, under the message *"This is what your instructions made the AI build."* Submit runs hidden browser and layout checks and feeds a normalized evaluation score into the existing score, stars, XP, progression, and leaderboards. Details and limitations: [CHALLENGE_TYPES.md](CHALLENGE_TYPES.md#application-prototype--implemented).

### Image and visual-prompt challenges — later phase

A future image challenge may show a target image while keeping its original generation prompt/configuration hidden. The player writes an image-generation prompt, sees the generated attempt beside the target, receives similarity and quality dimensions, and iterates.

Potential dimensions include subject, composition, style, semantic similarity, and overall visual similarity. This family is intentionally deferred until after the application prototype because model nondeterminism, seed/configuration consistency, generation cost, scoring quality, model-version comparability, and artifact storage materially affect fairness.

See [CHALLENGE_TYPES.md](CHALLENGE_TYPES.md) for why the direction changed, the detailed family model, application-challenge assets, the first prototype, isolation requirements, risks, and deferred decisions.

## Result visibility and feedback

Where meaningful and safe, Run should expose the actual AI output or artifact:

- A visible text Run may show the visible input, expected output, AI output, pass/fail decision, and diagnostic reason.
- An application Run may show the modified application preview or screenshot, build and test results, a patch summary, and safe requirement diagnostics.
- An image Run may show the target and generated image side by side with evaluation dimensions.

Submit remains an authoritative hidden evaluation. It must not reveal hidden inputs, expected outputs, hidden actual outputs when those expose the evaluation, or implementation details that make hidden checks reconstructable. Submit may return aggregate scoring, generalized failure categories, safe diagnostics, and carefully selected artifacts that do not compromise hidden evaluation integrity.

## Product systems to preserve

The revised direction builds on the existing platform rather than replacing it. The following are implemented foundations:

- Supabase authentication and durable local application users;
- PostgreSQL/Supabase persistence and versioned challenge definitions;
- separate visible and hidden tests with deterministic graders;
- provider-neutral model execution with a Groq adapter;
- authoritative prompt token counting, scoring, and stars;
- append-only XP milestones, progress, and derived challenge unlocking;
- challenge-specific leaderboards and the current-user profile;
- an admin challenge builder for TEXT and static APPLICATION packages; and
- the established frontend design system.

Stars, XP, progression, leaderboards, profiles, and versioning should ideally work across challenge families. A future challenge-specific executor should produce a normalized evaluation result that the existing competitive/progression layer can consume. Different families need not reduce quality to simple hidden-test accuracy; normalization and comparability require explicit design.

## Current implemented scope

The implemented product contains a five-challenge CONTROL path with visible Run, authenticated hidden Submit, scoring, stars, durable owned submissions, XP, progression, unlocking, profiles, challenge leaderboards, and admin authoring. It contains the challenge-execution boundary with a text executor and two APPLICATION challenges (Responsive Hero and Pricing Grid), including a coding-agent path, disposable workspaces, deterministic browser checks, and screenshot results. It does not yet contain an image executor, live previews, durable artifact storage, a full sandbox for executable agent code, executable-code challenges.

The earlier plan to immediately fill approximately twenty text challenges across CONTROL, EXTRACT, CLASSIFY, and STRUCTURE is no longer the immediate roadmap. Those tracks remain useful content categories, but catalog expansion follows validation of the application-challenge experiment.

## Roadmap

1. Preserve and stabilize the current text challenge system and five CONTROL foundations.
2. Generalize challenge execution contracts without regressing existing Run/Submit behavior.
3. Decide and validate an isolated/disposable workspace strategy for coding-agent execution. *(Prototype: local disposable workspace; full sandbox still open.)*
4. Build exactly one small application challenge prototype. *(Done: Responsive Hero.)*
5. Add safe result and artifact viewing to the player experience. *(Done for the prototype.)*
6. Evaluate engagement, fairness, reproducibility, latency, and model/runtime cost.
7. Build reusable application-challenge authoring, execution, and artifact infrastructure. *(Done: Platform v1; see [APPLICATION_PLATFORM.md](APPLICATION_PLATFORM.md).)*
8. Validate the two-challenge applied catalog before expanding further.
9. Explore one image-generation challenge prototype later.
10. Finalize the broader track and catalog distribution only after those experiments.

Already-completed authentication, persistence, evaluation, progression, leaderboard, profile, and admin features remain complete foundations in this roadmap.

## Success criteria

In addition to reliable scoring and voluntary retry rate, the applied direction should demonstrate that:

- players understand that their instructions—not direct editing—control the AI;
- players inspect the AI-produced result before revising their prompt;
- failures are understandable from the result plus safe diagnostics;
- revisions respond to observed AI behavior rather than blind score chasing;
- functional evaluation feels fair and reproducible;
- isolated execution is reliable and does not expose trusted infrastructure; and
- model, execution, and artifact costs remain sustainable.

## XP milestones — implemented

Completion means earning at least one star. A normal challenge awards first completion (100 XP), two stars (25 XP), and three stars (50 XP) at most once each; a first three-star result therefore earns 175 XP. For a future BOSS challenge, the 250 XP boss-completion milestone replaces normal first-completion XP by default while two- and three-star milestones remain independently available. XP is ledger-derived and repeat submissions cannot farm an already earned milestone. These rules are intended to apply unchanged to future challenge families.

## Challenge progression — implemented

Published challenges are ordered within a track. The first challenge is available by default; each later challenge becomes available when the immediately preceding challenge has `best_stars >= 1`. Zero-star attempts do not unlock anything. Completed challenges remain replayable, and a three-star challenge is mastered. Unlock state is derived from authoritative progress rather than stored as mutable state. Both initial APPLICATION challenges follow the CONTROL foundations in the same track; a dedicated applied track remains deferred.

## Durable terminology

- **Challenge:** a versioned task definition, execution configuration, visible guidance, and evaluation policy. Different families may also own versioned environment assets.
- **Challenge family/type:** the execution and result shape, such as text, application, or image.
- **Run:** visible evaluation with debugging-oriented output and safe result artifacts.
- **Submit:** authoritative hidden evaluation with sanitized feedback.
- **Executor:** a family-specific component that turns a player prompt plus a versioned challenge environment into an internal normalized execution result. TEXT and static APPLICATION executors are implemented.
- **Artifact:** an inspectable product of execution, such as generated text, a patch summary, build report, screenshot, application preview, or image.
- **Grader/check:** programmatic evaluation of an output, artifact, or environment state.
- **Hidden test/check:** server-only evaluation data or logic used to measure generalization.
- **Accuracy:** for text challenges, the proportion of tests passed; combined with efficiency by challenge-specific weights. Internally this is the text family's normalized evaluation score; other families are expected to supply their own normalized score in its place.
- **Efficiency:** a prompt-cost measure based on the player prompt's token count.
- **XP milestone:** a server-awarded, one-time achievement for a challenge.
- **Challenge leaderboard:** comparable best results for a challenge's active version and execution configuration.
