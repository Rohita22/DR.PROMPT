import type { AdminTestResult, ChallengeDefinition } from "./types";

type ErrorPayload = { error?: { message?: string }; detail?: string };

async function adminRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/admin/challenges${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  const payload = (await response.json().catch(() => ({}))) as T & ErrorPayload;
  if (!response.ok) {
    throw new Error(payload.error?.message ?? payload.detail ?? "Admin request failed.");
  }
  return payload;
}

export function saveChallenge(challenge: ChallengeDefinition, isNew: boolean) {
  const definition: Partial<ChallengeDefinition> = { ...challenge };
  delete definition.id;
  delete definition.current_version;
  delete definition.versions;
  delete definition.created_at;
  delete definition.updated_at;
  return adminRequest<{ message: string }>(isNew ? "" : `/${challenge.slug}`, {
    method: isNew ? "POST" : "PUT",
    body: JSON.stringify({ ...definition, publication_state: "draft" }),
  });
}

export function createVersion(slug: string) {
  return adminRequest<{ message: string; version: string }>(`/${slug}/versions`, { method: "POST" });
}

export function publishChallenge(slug: string, version: string) {
  return adminRequest<{ message: string }>(`/${slug}/publish`, {
    method: "POST",
    body: JSON.stringify({ version }),
  });
}

export function unpublishChallenge(slug: string) {
  return adminRequest<{ message: string }>(`/${slug}/unpublish`, {
    method: "POST",
    body: "{}",
  });
}

export function testChallenge(slug: string, prompt: string) {
  return adminRequest<AdminTestResult>(`/${slug}/test`, {
    method: "POST",
    body: JSON.stringify({ prompt }),
  });
}

export async function checkPackageHealth(id: string): Promise<{available: boolean; build_succeeded: boolean | null; checks_initialized: boolean}> {
  const response = await fetch(`/api/admin/application-packages/${encodeURIComponent(id)}/health`, {method:"POST"});
  if (!response.ok) throw new Error("Package health could not be verified.");
  return response.json();
}
