import { afterEach, describe, expect, it, vi } from "vitest";

import { saveChallenge, testChallenge } from "./api";
import { emptyChallenge } from "./types";

afterEach(() => vi.restoreAllMocks());

describe("admin browser API", () => {
  it("uses the same-origin BFF and never attaches an admin key", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ message: "saved" }), { status: 200 }),
    );
    const challenge = emptyChallenge();
    challenge.slug = "new-challenge";
    await saveChallenge(challenge, true);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/admin/challenges");
    expect(init?.headers).not.toHaveProperty("X-Admin-Key");
    expect(JSON.stringify(init)).not.toContain("ADMIN_API_KEY");
  });

  it("sends candidate prompts only to the protected test route", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ challenge: "exact-output" }), { status: 200 }),
    );
    await testChallenge("exact-output", "Return YES or NO.");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/admin/challenges/exact-output/test",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ prompt: "Return YES or NO." }) }),
    );
  });
});
