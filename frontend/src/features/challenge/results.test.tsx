import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { RunResults, SubmitResults } from "./results";

describe("challenge result views", () => {
  it("renders detailed visible Run feedback", () => {
    const markup = renderToStaticMarkup(
      <RunResults
        result={{
          challenge: "exact-output",
          challenge_id: "control-exact-output",
          version: "1",
          passed: 1,
          total: 2,
          accuracy: 50,
          tests: [
            {
              id: "visible-1",
              input: "Service is online.",
              expected: "YES",
              actual: "NO",
              passed: false,
              failure_reason: "output_mismatch",
            },
          ],
        }}
      />,
    );

    expect(markup).toContain("Service is online.");
    expect(markup).toContain("Expected");
    expect(markup).toContain("Actual");
    expect(markup).toContain("FAIL");
  });

  it("renders aggregate Submit scoring with no hidden-test collection", () => {
    const markup = renderToStaticMarkup(
      <SubmitResults
        result={{
          challenge: "exact-output",
          version: "1",
          passed: 5,
          total: 6,
          accuracy: 83.33,
          prompt_tokens: 42,
          efficiency: 100,
          score: 86.66,
          stars: 1,
          xp_earned: 100,
          total_xp: 100,
          best_score: 86.66,
          best_stars: 1,
          completed: true,
        }}
      />,
    );

    expect(markup).toContain("83.33%");
    expect(markup).toContain("86.66");
    expect(markup).toContain("1/3");
    expect(markup).toContain("XP earned");
    expect(markup).toContain("Total XP");
    expect(markup).not.toContain("hidden-");
    expect(markup).not.toContain("Expected");
    expect(markup).not.toContain("Actual");
  });
});
