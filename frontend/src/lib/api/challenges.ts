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

export type Screenshot = {
  label?: string;
  viewport: string;
  width: number;
  height: number;
  image: string;
};

export type ApplicationCheckResult = {
  id: string;
  label: string;
  passed: boolean;
  message: string | null;
};

export type ApplicationRunResponse = {
  challenge_type: "application";
  challenge: string;
  challenge_id: string;
  version: string;
  passed: number;
  total: number;
  evaluation_score: number;
  agent: { status: "applied" | "rejected"; message: string | null };
  changed_files: Array<{ path: string; additions: number; deletions: number }>;
  build: { status: "passed" | "failed" | "skipped"; log: string };
  checks: ApplicationCheckResult[];
  screenshots: Screenshot[];
};

export type ApplicationSubmitResponse = {
  challenge_type: "application";
  challenge: string;
  version: string;
  passed: number;
  total: number;
  evaluation_score: number;
  prompt_tokens: number;
  efficiency: number;
  score: number;
  stars: number;
  xp_earned: number;
  total_xp: number;
  best_score: number;
  best_stars: number;
  completed: boolean;
  agent_status: "applied" | "rejected";
  screenshot: Screenshot | null;
};

export type AnyRunResponse = RunChallengeResponse | ApplicationRunResponse;
export type AnySubmitResponse = SubmitChallengeResponse | ApplicationSubmitResponse;

export function isApplicationRun(result: AnyRunResponse): result is ApplicationRunResponse {
  return "challenge_type" in result && result.challenge_type === "application";
}

export function isApplicationSubmit(result: AnySubmitResponse): result is ApplicationSubmitResponse {
  return "challenge_type" in result && result.challenge_type === "application";
}

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

export type ProfileActivity = {
  challenge: string;
  title: string;
  score: number;
  accuracy: number;
  stars: number;
  prompt_tokens: number;
  xp_earned: number;
  submitted_at: string;
};

export type CurrentUserProfileResponse = {
  player: string;
  level: number;
  level_progress: {
    level_floor: number;
    next_level_at: number;
    earned_in_level: number;
    required_in_level: number;
  };
  total_xp: number;
  challenges: { completed: number; total: number };
  stars: { earned: number; total: number };
  three_star_completions: number;
  best_leaderboard_position: number | null;
  recent_activity: ProfileActivity[];
};

export type ChallengeStatus = "locked" | "available" | "completed" | "mastered";

export type ChallengeListItem = {
  id: string;
  slug: string;
  title: string;
  track: string;
  challenge_type: string;
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
  application: { execution_mode?: "static" | "sandboxed_executable"; available?: boolean; editable_files: string[]; starter_preview_viewports: string[] } | null;
};

export type LeaderboardEntry = {
  rank: number;
  player: string;
  score: number;
  accuracy: number;
  prompt_tokens: number;
  stars: number;
  submitted_at: string;
  is_current_user: boolean;
};

export type ChallengeLeaderboardResponse = {
  challenge: string;
  version: string;
  entries: LeaderboardEntry[];
  current_user_entry: LeaderboardEntry | null;
  total_entries: number;
  limit: number;
  offset: number;
  has_more: boolean;
};

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string | null = null,
    readonly retryAfterSeconds: number | null = null,
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
  const retryAfterHeader = response.headers.get("Retry-After");
  const retryAfterSeconds = retryAfterHeader !== null && /^\d+$/.test(retryAfterHeader)
    ? Number(retryAfterHeader)
    : null;
  try {
    const body: unknown = await response.json();
    if (typeof body === "object" && body !== null && "error" in body) {
      const error = body.error;
      if (typeof error === "object" && error !== null) {
        const message = "message" in error && typeof error.message === "string"
          ? error.message
          : "The request failed.";
        const code = "code" in error && typeof error.code === "string" ? error.code : null;
        return new ApiError(message, response.status, code, retryAfterSeconds);
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
  extraHeaders: Record<string, string> = {},
): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json", ...extraHeaders };
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
  accessToken: string | null = null,
  fetcher: typeof fetch = fetch,
): Promise<AnyRunResponse> {
  // Run is optionally authenticated: later challenges require the player's progression.
  return postPrompt(
    `/api/v1/challenges/${encodeURIComponent(challengeSlug)}/run`,
    prompt,
    accessToken,
    fetcher,
  );
}

export function getStarterPreviewUrl(challengeSlug: string, viewport: string): string {
  return `${getApiBaseUrl()}/api/v1/challenges/${encodeURIComponent(challengeSlug)}/starter-preview/${encodeURIComponent(viewport)}.png`;
}

export function submitChallenge(
  challengeSlug: string,
  prompt: string,
  accessToken: string | null,
  fetcher: typeof fetch = fetch,
  idempotencyKey: string | null = null,
): Promise<AnySubmitResponse> {
  if (accessToken === null) {
    throw new AuthRequiredError();
  }
  return postPrompt(
    `/api/v1/challenges/${encodeURIComponent(challengeSlug)}/submit`,
    prompt,
    accessToken,
    fetcher,
    idempotencyKey === null ? {} : { "Idempotency-Key": idempotencyKey },
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

export function getChallengeLeaderboard(
  challengeSlug: string,
  accessToken: string | null,
  limit = 25,
  offset = 0,
  fetcher: typeof fetch = fetch,
): Promise<ChallengeLeaderboardResponse> {
  const query = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  return getChallengeResource(
    `/api/v1/challenges/${encodeURIComponent(challengeSlug)}/leaderboard?${query}`,
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

export async function getCurrentUserProfile(
  accessToken: string,
  fetcher: typeof fetch = fetch,
): Promise<CurrentUserProfileResponse> {
  let response: Response;
  try {
    response = await fetcher(`${getApiBaseUrl()}/api/v1/me/profile`, {
      headers: { Authorization: `Bearer ${accessToken}` },
      cache: "no-store",
    });
  } catch {
    throw new ApiError("The backend is unavailable.", 0);
  }
  if (!response.ok) {
    throw await parseError(response);
  }
  return (await response.json()) as CurrentUserProfileResponse;
}

export function getReadableError(error: unknown): string {
  if (error instanceof AuthRequiredError || error instanceof ApiError) {
    return error.message;
  }
  return "The request failed unexpectedly.";
}

export function getApplicationExecutionError(
  error: unknown,
  kind: "run" | "submit",
): string {
  if (!(error instanceof ApiError)) return getReadableError(error);
  if (error.code === "application_rate_limited") {
    const seconds = error.retryAfterSeconds ?? 1;
    return `Application ${kind === "run" ? "runs" : "submissions"} can be retried in ${seconds} seconds.`;
  }
  if (error.code === "application_execution_in_progress") {
    return "The coding agent is already working on an application attempt.";
  }
  if (error.code === "llm_rate_limit_error") {
    return "The AI service is temporarily busy. Try again shortly.";
  }
  return getReadableError(error);
}
