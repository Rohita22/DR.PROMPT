import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  AuthRequiredError,
  getCurrentUserProgress,
  getCurrentUserProfile,
  getChallengeLeaderboard,
  getChallengeDetail,
  getChallenges,
  getStarterPreviewUrl,
  getApplicationExecutionError,
  isApplicationRun,
  runChallenge,
  submitChallenge,
} from "./challenges";

describe("challenge API client", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("runs without authentication headers", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.example.test");
    const responseBody = {
      challenge: "exact-output",
      challenge_id: "control-exact-output",
      version: "1",
      passed: 1,
      total: 1,
      accuracy: 100,
      tests: [],
    };
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify(responseBody), { status: 200 }),
    );

    await expect(runChallenge("formatting-rules", "Return YES.", null, fetcher)).resolves.toEqual(
      responseBody,
    );
    expect(fetcher.mock.calls[0][0]).toContain("/formatting-rules/run");
    const [, options] = fetcher.mock.calls[0];
    expect(options?.headers).toEqual({ "Content-Type": "application/json" });
  });

  it("attaches the access token to runs of progression-gated challenges", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.example.test");
    const responseBody = {
      challenge_type: "application",
      challenge: "responsive-hero",
      challenge_id: "control-responsive-hero",
      version: "1",
      passed: 4,
      total: 4,
      evaluation_score: 100,
      agent: { status: "applied", message: null },
      changed_files: [],
      build: { status: "passed", log: "" },
      checks: [],
      screenshots: [],
    };
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify(responseBody), { status: 200 }),
    );

    const result = await runChallenge("responsive-hero", "Make it responsive.", "access-token", fetcher);

    expect(isApplicationRun(result)).toBe(true);
    expect(fetcher.mock.calls[0][1]?.headers).toEqual({
      "Content-Type": "application/json",
      Authorization: "Bearer access-token",
    });
    expect(getStarterPreviewUrl("responsive-hero", "desktop")).toBe(
      "http://api.example.test/api/v1/challenges/responsive-hero/starter-preview/desktop.png",
    );
  });

  it("blocks logged-out submissions before a request is sent", () => {
    const fetcher = vi.fn<typeof fetch>();

    expect(() => submitChallenge("exact-output", "Return YES.", null, fetcher)).toThrow(
      AuthRequiredError,
    );
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("attaches the access token to authenticated submissions", async () => {
    const responseBody = {
      challenge: "exact-output",
      version: "1",
      passed: 6,
      total: 6,
      accuracy: 100,
      prompt_tokens: 8,
      efficiency: 100,
      score: 100,
      stars: 3,
      xp_earned: 175,
      total_xp: 175,
      best_score: 100,
      best_stars: 3,
      completed: true,
    };
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify(responseBody), { status: 200 }),
    );

    await expect(
      submitChallenge("control-boss", "Return YES.", "access-token", fetcher),
    ).resolves.toEqual(responseBody);
    expect(fetcher.mock.calls[0][0]).toContain("/control-boss/submit");
    const [, options] = fetcher.mock.calls[0];
    expect(options?.headers).toEqual({
      "Content-Type": "application/json",
      Authorization: "Bearer access-token",
    });
    expect(options?.body).toBe(JSON.stringify({ prompt: "Return YES." }));
    expect(options?.body).not.toContain("user_id");
    expect(options?.body).not.toContain("xp_earned");
    expect(options?.body).not.toContain("best_score");
  });

  it("sends one opaque idempotency key for an application Submit action", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ challenge_type: "application" }), { status: 200 }),
    );

    await submitChallenge(
      "responsive-hero",
      "Make it responsive.",
      "access-token",
      fetcher,
      "submit-action-123",
    );

    expect(fetcher.mock.calls[0][1]?.headers).toEqual({
      "Content-Type": "application/json",
      Authorization: "Bearer access-token",
      "Idempotency-Key": "submit-action-123",
    });
  });

  it("loads authenticated current-user progress", async () => {
    const responseBody = {
      total_xp: 175,
      challenges_completed: 1,
      stars_earned: 3,
      challenges: [],
    };
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify(responseBody), { status: 200 }),
    );

    await expect(getCurrentUserProgress("access-token", fetcher)).resolves.toEqual(responseBody);
    expect(fetcher.mock.calls[0][1]?.headers).toEqual({
      Authorization: "Bearer access-token",
    });
  });

  it("loads the authenticated profile without sending trusted game state", async () => {
    const responseBody = {
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
      recent_activity: [],
    };
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify(responseBody), { status: 200 }),
    );

    await expect(getCurrentUserProfile("access-token", fetcher)).resolves.toEqual(responseBody);
    expect(fetcher.mock.calls[0][0]).toContain("/api/v1/me/profile");
    expect(fetcher.mock.calls[0][1]).toEqual({
      headers: { Authorization: "Bearer access-token" },
      cache: "no-store",
    });
  });

  it("loads challenge catalog and selected detail with optional authentication", async () => {
    const fetcher = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(JSON.stringify({ challenges: [] }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ slug: "exact-output" }), { status: 200 }));

    await getChallenges(null, fetcher);
    await getChallengeDetail("exact-output", "access-token", fetcher);

    expect(fetcher.mock.calls[0][1]?.headers).toEqual({});
    expect(fetcher.mock.calls[1][1]?.headers).toEqual({
      Authorization: "Bearer access-token",
    });
  });

  it("loads a paginated public or authenticated challenge leaderboard", async () => {
    const responseBody = {
      challenge: "formatting-rules",
      version: "1",
      entries: [],
      current_user_entry: null,
      total_entries: 0,
      limit: 10,
      offset: 20,
      has_more: false,
    };
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify(responseBody), { status: 200 }),
    );

    await expect(
      getChallengeLeaderboard("formatting-rules", "access-token", 10, 20, fetcher),
    ).resolves.toEqual(responseBody);
    expect(fetcher.mock.calls[0][0]).toContain(
      "/formatting-rules/leaderboard?limit=10&offset=20",
    );
    expect(fetcher.mock.calls[0][1]?.headers).toEqual({
      Authorization: "Bearer access-token",
    });
  });

  it("surfaces safe backend errors", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          error: { code: "prompt_too_long", message: "Prompt exceeds the token limit." },
        }),
        { status: 422 },
      ),
    );

    await expect(
      submitChallenge("exact-output", "long prompt", "access-token", fetcher),
    ).rejects.toEqual(
      new ApiError("Prompt exceeds the token limit.", 422, "prompt_too_long"),
    );
  });

  it("preserves Retry-After and maps application execution errors safely", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          error: {
            code: "application_rate_limited",
            message: "Application runs can be retried in 7 seconds.",
          },
        }),
        { status: 429, headers: { "Retry-After": "7" } },
      ),
    );

    let error: unknown;
    try {
      await runChallenge("responsive-hero", "Improve it.", "access-token", fetcher);
    } catch (caught) {
      error = caught;
    }
    expect(error).toEqual(
      new ApiError(
        "Application runs can be retried in 7 seconds.",
        429,
        "application_rate_limited",
        7,
      ),
    );
    expect(getApplicationExecutionError(error, "run")).toBe(
      "Application runs can be retried in 7 seconds.",
    );
    expect(
      getApplicationExecutionError(
        new ApiError("provider detail", 429, "llm_rate_limit_error"),
        "run",
      ),
    ).toBe("The AI service is temporarily busy. Try again shortly.");
  });

  it("reports backend unavailability without leaking fetch errors", async () => {
    const fetcher = vi.fn<typeof fetch>().mockRejectedValue(new Error("socket detail"));

    await expect(runChallenge("exact-output", "Return YES.", null, fetcher)).rejects.toEqual(
      new ApiError("The backend is unavailable.", 0),
    );
  });
});
