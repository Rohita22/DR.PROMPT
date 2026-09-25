import { getApiBaseUrl } from "./config";

export type HealthResponse = {
  status: "ok";
  service: "dr-prompt-api";
};

export type BackendHealth = HealthResponse | { status: "unavailable" };

export async function getBackendHealth(fetcher: typeof fetch = fetch): Promise<BackendHealth> {
  try {
    const response = await fetcher(`${getApiBaseUrl()}/api/v1/health`, {
      cache: "no-store",
    });

    if (!response.ok) {
      return { status: "unavailable" };
    }

    const body: unknown = await response.json();
    if (
      typeof body === "object" &&
      body !== null &&
      "status" in body &&
      body.status === "ok" &&
      "service" in body &&
      body.service === "dr-prompt-api"
    ) {
      return body as HealthResponse;
    }
  } catch {
    // The development shell remains usable while the API is stopped.
  }

  return { status: "unavailable" };
}

