import { getApiBaseUrl } from "./config";

export type VisibleTestResult = {
  id: string;
  input: unknown;
  expected: unknown;
  actual: unknown;
  passed: boolean;
  failure_reason: string | null;
};

export type RunChallengeResponse = {
  challenge: string;
  challenge_id: string;
  version: string;
  passed: number;
  total: number;
  accuracy: number;
  tests: VisibleTestResult[];
};

export type SubmitChallengeResponse = {
  challenge: string;
  version: string;
  passed: number;
  total: number;
  accuracy: number;
  prompt_tokens: number;
  efficiency: number;
  score: number;
  stars: number;
  xp_earned: number;
  total_xp: number;
  best_score: number;
  best_stars: number;
  completed: boolean;
};

export type CurrentUserResponse = {
  id: string;
  email: string | null;
  username: string | null;
};

export type ChallengeProgress = {
  challenge: string;
  best_score: number;
  best_stars: number;
  attempts: number;
  completed: boolean;
  completed_at: string | null;
};

export type CurrentUserProgressResponse = {
  total_xp: number;
  challenges_completed: number;
  stars_earned: number;
  challenges: ChallengeProgress[];
};

export type ChallengeStatus = "locked" | "available" | "completed" | "mastered";

export type ChallengeListItem = {
  id: string;
  slug: string;
  title: string;
  track: string;
  difficulty: string;
  order: number;
  status: ChallengeStatus;
  best_score: number | null;
  best_stars: number;
  attempts: number;
  completed: boolean;
};

export type ChallengeListResponse = { challenges: ChallengeListItem[] };

export type ChallengeDetailResponse = ChallengeListItem & {
  description: string;
  objective: string;
  constraints: string[];
  version: string;
  prompt_token_limit: number | null;
  examples: Array<{ input: unknown; expected: unknown; explanation: string | null }>;
};

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string | null = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export class AuthRequiredError extends Error {
  constructor() {
    super("Sign in before submitting a challenge.");
    this.name = "AuthRequiredError";
  }
}

async function parseError(response: Response): Promise<ApiError> {
  try {
    const body: unknown = await response.json();
    if (typeof body === "object" && body !== null && "error" in body) {
      const error = body.error;
      if (typeof error === "object" && error !== null) {
        const message = "message" in error && typeof error.message === "string"
          ? error.message
          : "The request failed.";
        const code = "code" in error && typeof error.code === "string" ? error.code : null;
        return new ApiError(message, response.status, code);
      }
    }
  } catch {
    // Fall through to a safe generic error.
  }
  return new ApiError("The request failed.", response.status);
}

async function postPrompt<T>(
  path: string,
  prompt: string,
  accessToken: string | null,
  fetcher: typeof fetch,
): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (accessToken !== null) {
    headers.Authorization = `Bearer ${accessToken}`;
  }
  let response: Response;
  try {
    response = await fetcher(`${getApiBaseUrl()}${path}`, {
      method: "POST",
      headers,
      body: JSON.stringify({ prompt }),
    });
  } catch {
    throw new ApiError("The backend is unavailable.", 0);
  }
  if (!response.ok) {
    throw await parseError(response);
  }
  return (await response.json()) as T;
}

export function runChallenge(
  challengeSlug: string,
  prompt: string,
  fetcher: typeof fetch = fetch,
): Promise<RunChallengeResponse> {
  return postPrompt(
    `/api/v1/challenges/${encodeURIComponent(challengeSlug)}/run`,
    prompt,
    null,
    fetcher,
  );
}

export function submitChallenge(
  challengeSlug: string,
  prompt: string,
  accessToken: string | null,
  fetcher: typeof fetch = fetch,
): Promise<SubmitChallengeResponse> {
  if (accessToken === null) {
    throw new AuthRequiredError();
  }
  return postPrompt(
    `/api/v1/challenges/${encodeURIComponent(challengeSlug)}/submit`,
    prompt,
    accessToken,
    fetcher,
  );
}

async function getChallengeResource<T>(
  path: string,
  accessToken: string | null,
  fetcher: typeof fetch,
): Promise<T> {
  const headers: Record<string, string> = {};
  if (accessToken !== null) headers.Authorization = `Bearer ${accessToken}`;
  let response: Response;
  try {
    response = await fetcher(`${getApiBaseUrl()}${path}`, { headers, cache: "no-store" });
  } catch {
    throw new ApiError("The backend is unavailable.", 0);
  }
  if (!response.ok) throw await parseError(response);
  return (await response.json()) as T;
}

export function getChallenges(
  accessToken: string | null,
  fetcher: typeof fetch = fetch,
): Promise<ChallengeListResponse> {
  return getChallengeResource("/api/v1/challenges", accessToken, fetcher);
}

export function getChallengeDetail(
  challengeSlug: string,
  accessToken: string | null,
  fetcher: typeof fetch = fetch,
): Promise<ChallengeDetailResponse> {
  return getChallengeResource(
    `/api/v1/challenges/${encodeURIComponent(challengeSlug)}`,
    accessToken,
    fetcher,
  );
}

export async function getCurrentUser(
  accessToken: string,
  fetcher: typeof fetch = fetch,
): Promise<CurrentUserResponse> {
  let response: Response;
  try {
    response = await fetcher(`${getApiBaseUrl()}/api/v1/me`, {
      headers: { Authorization: `Bearer ${accessToken}` },
      cache: "no-store",
    });
  } catch {
    throw new ApiError("The backend is unavailable.", 0);
  }
  if (!response.ok) {
    throw await parseError(response);
  }
  return (await response.json()) as CurrentUserResponse;
}

export async function getCurrentUserProgress(
  accessToken: string,
  fetcher: typeof fetch = fetch,
): Promise<CurrentUserProgressResponse> {
  let response: Response;
  try {
    response = await fetcher(`${getApiBaseUrl()}/api/v1/me/progress`, {
      headers: { Authorization: `Bearer ${accessToken}` },
      cache: "no-store",
    });
  } catch {
    throw new ApiError("The backend is unavailable.", 0);
  }
  if (!response.ok) {
    throw await parseError(response);
  }
  return (await response.json()) as CurrentUserProgressResponse;
}

export function getReadableError(error: unknown): string {
  if (error instanceof AuthRequiredError || error instanceof ApiError) {
    return error.message;
  }
  return "The request failed unexpectedly.";
}
