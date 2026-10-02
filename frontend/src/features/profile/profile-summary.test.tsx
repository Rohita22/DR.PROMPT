import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import type { CurrentUserProfileResponse } from "@/lib/api/challenges";

import { ProfileError, ProfileLoading, ProfileSummary } from "./profile-summary";

function profile(
  overrides: Partial<CurrentUserProfileResponse> = {},
): CurrentUserProfileResponse {
  return {
    player: "Player-A1B2",
    level: 2,
    level_progress: {
      level_floor: 500,
      next_level_at: 1000,
      earned_in_level: 340,
      required_in_level: 500,
    },
    total_xp: 840,
    challenges: { completed: 4, total: 5 },
    stars: { earned: 10, total: 15 },
    three_star_completions: 2,
    best_leaderboard_position: 7,
    recent_activity: [{
      challenge: "formatting-rules",
      title: "Formatting Rules",
      score: 94.5,
      accuracy: 100,
      stars: 2,
      prompt_tokens: 81,
      xp_earned: 25,
      submitted_at: "2026-01-02T10:00:00Z",
    }],
    ...overrides,
  };
}

describe("profile summary", () => {
  it("renders authoritative statistics and recent activity", () => {
    const markup = renderToStaticMarkup(
      <ProfileSummary profile={profile()} onSignOut={vi.fn()} />,
    );

    expect(markup).toContain("Player-A1B2");
    expect(markup).toContain("Level 2");
    expect(markup).toContain("840 total XP");
    expect(markup).toContain("4");
    expect(markup).toContain(" / 5");
    expect(markup).toContain("10");
    expect(markup).toContain(" / 15");
    expect(markup).toContain("#7");
    expect(markup).toContain("Formatting Rules");
    expect(markup).toContain("94.5");
    expect(markup).toContain("+25");
    expect(markup).not.toContain("private@example.com");
    expect(markup).not.toContain("provider-subject");
    expect(markup).not.toContain("player prompt");
  });

  it("renders a useful empty state for a new player", () => {
    const markup = renderToStaticMarkup(
      <ProfileSummary
        profile={profile({
          level: 1,
          total_xp: 0,
          challenges: { completed: 0, total: 5 },
          stars: { earned: 0, total: 15 },
          three_star_completions: 0,
          best_leaderboard_position: null,
          recent_activity: [],
        })}
        onSignOut={vi.fn()}
      />,
    );

    expect(markup).toContain("Your first score starts here.");
    expect(markup).toContain("Play the first challenge");
    expect(markup).toContain("href=\"/play\"");
  });

  it("renders established loading and retryable error states", () => {
    const loading = renderToStaticMarkup(<ProfileLoading />);
    const error = renderToStaticMarkup(
      <ProfileError message="The backend is unavailable." onRetry={vi.fn()} />,
    );

    expect(loading).toContain("Loading your profile");
    expect(loading).toContain("aria-busy=\"true\"");
    expect(error).toContain("We couldn’t load your profile.");
    expect(error).toContain("The backend is unavailable.");
    expect(error).toContain("Try again");
  });
});
