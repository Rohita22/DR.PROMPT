# Product

DR. PROMPT is a technical skill game for learning prompt engineering through objective, hands-on challenges. It is designed for developers, technical learners, and prompt practitioners who learn best by solving and refining rather than watching a course.

## Core loop and hypothesis

The loop is **Write → Run → Submit → Diagnose → Improve**. A player writes a prompt, runs it against visible examples, submits it against hidden cases, reads a score and safe feedback, then retries.

The core hypothesis is that players will voluntarily replay completed challenges to improve both their score and the robustness of their prompts.

## MVP boundaries

The planned MVP contains roughly 20 curated challenges across CONTROL, EXTRACT, CLASSIFY, and STRUCTURE, ending in a combined final challenge. This foundation contains no playable challenges. It also deliberately excludes accounts, persistence, provider calls, evaluation, scoring, progression, leaderboards, administration, analytics, and deployment infrastructure.

## Terminology

- **Challenge:** a prompt-engineering problem with an objective, constraints, examples, and grading configuration.
- **Run:** evaluation against visible tests with debugging-oriented details.
- **Submit:** authoritative evaluation against secret server-side tests with a sanitized result.
- **Grader:** interchangeable programmatic logic that compares model output with an expected result.
- **Accuracy:** the proportion of tests passed; planned to contribute 80% of the initial score.
- **Efficiency:** a prompt-cost measure based mainly on token count; planned to contribute 20%.
- **Hidden test:** a server-only input and expected output used to measure generalization.

