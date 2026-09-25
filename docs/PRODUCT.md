# Product

DR. PROMPT is a technical skill game for learning prompt engineering through objective, hands-on challenges. It is designed for developers, technical learners, and prompt practitioners who learn best by solving and refining rather than watching a course.

## Core loop and hypothesis

The loop is **Write → Run → Submit → Diagnose → Improve**. A player writes a prompt, runs it against visible examples, submits it against hidden cases, reads a score and safe feedback, then retries.

The core hypothesis is that players will voluntarily replay completed challenges to improve both their score and the robustness of their prompts.

## MVP boundaries

The planned MVP contains roughly 20 curated challenges across CONTROL, EXTRACT, CLASSIFY, and STRUCTURE, ending in a combined final challenge. The current prototype contains a five-challenge CONTROL path with visible Run, authenticated server-only Submit evaluation, challenge-configured scoring and stars, durable local users, owned submissions, an append-only XP ledger, and derived challenge unlocking. It deliberately excludes the remaining tracks, username onboarding, profiles, leaderboards, administration, analytics, and deployment infrastructure.

## Terminology

- **Challenge:** a prompt-engineering problem with an objective, constraints, examples, and grading configuration.
- **Run:** evaluation against visible tests with debugging-oriented details.
- **Submit:** authoritative evaluation against secret server-side tests with a sanitized result.
- **Grader:** interchangeable programmatic logic that compares model output with an expected result.
- **Accuracy:** the proportion of tests passed; planned to contribute 80% of the initial score.
- **Efficiency:** a prompt-cost measure based mainly on token count; planned to contribute 20%.
- **Hidden test:** a server-only input and expected output used to measure generalization.
- **XP milestone:** a server-awarded, one-time achievement for a challenge: first completion, two stars, three stars, or boss completion.

## XP milestones

Completion means earning at least one star. A normal challenge awards first completion (100 XP), two stars (25 XP), and three stars (50 XP) at most once each; a first three-star result therefore earns 175 XP. For a future BOSS challenge, the 250 XP boss-completion milestone replaces normal first-completion XP by default while two- and three-star milestones remain independently available. XP is ledger-derived and repeat submissions cannot farm an already earned milestone.

## Challenge progression

Published challenges are ordered within a track. The first challenge is available by default; each later challenge becomes available when the immediately preceding challenge has `best_stars >= 1`. Zero-star attempts do not unlock anything. Completed challenges remain replayable, and a three-star challenge is mastered. Unlock state is derived from authoritative progress rather than stored as mutable state.
