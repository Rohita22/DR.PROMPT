import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { Leaderboard } from "./leaderboard";

describe("leaderboard harness view", () => {
  it("renders safe rankings and an out-of-page current-user position", () => {
    const markup = renderToStaticMarkup(
      <Leaderboard
        result={{
          challenge: "exact-output",
          version: "1",
          entries: [{
            rank: 1,
            player: "aiwizard",
            score: 98.4,
            accuracy: 100,
            prompt_tokens: 52,
            stars: 3,
            submitted_at: "2026-01-01T00:00:00Z",
            is_current_user: false,
          }],
          current_user_entry: {
            rank: 18,
            player: "Player-A12F",
            score: 91.4,
            accuracy: 90,
            prompt_tokens: 71,
            stars: 2,
            submitted_at: "2026-01-02T00:00:00Z",
            is_current_user: true,
          },
          total_entries: 18,
          limit: 1,
          offset: 0,
          has_more: true,
        }}
        onPrevious={vi.fn()}
        onNext={vi.fn()}
      />,
    );

    expect(markup).toContain("aiwizard");
    expect(markup).toContain("Your position: #18");
    expect(markup).toContain("Next");
    expect(markup).not.toContain("prompt");
    expect(markup).not.toContain("email");
  });
});
