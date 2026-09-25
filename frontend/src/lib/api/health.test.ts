import { afterEach, describe, expect, it, vi } from "vitest";

import { getBackendHealth } from "./health";

describe("getBackendHealth", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("returns a typed healthy response", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.example.test/");
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok", service: "dr-prompt-api" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(getBackendHealth(fetcher)).resolves.toEqual({
      status: "ok",
      service: "dr-prompt-api",
    });
    expect(fetcher).toHaveBeenCalledWith("http://api.example.test/api/v1/health", {
      cache: "no-store",
    });
  });

  it("degrades cleanly when the backend cannot be reached", async () => {
    const fetcher = vi.fn<typeof fetch>().mockRejectedValue(new Error("offline"));

    await expect(getBackendHealth(fetcher)).resolves.toEqual({ status: "unavailable" });
  });
});

