import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  AuthRequiredError,
  getCurrentUserProgress,
  getChallengeDetail,
  getChallenges,
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

    await expect(runChallenge("formatting-rules", "Return YES.", fetcher)).resolves.toEqual(
      responseBody,
    );
    expect(fetcher.mock.calls[0][0]).toContain("/formatting-rules/run");
    const [, options] = fetcher.mock.calls[0];
    expect(options?.headers).toEqual({ "Content-Type": "application/json" });
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

  it("reports backend unavailability without leaking fetch errors", async () => {
    const fetcher = vi.fn<typeof fetch>().mockRejectedValue(new Error("socket detail"));

    await expect(runChallenge("exact-output", "Return YES.", fetcher)).rejects.toEqual(
      new ApiError("The backend is unavailable.", 0),
    );
  });
});
