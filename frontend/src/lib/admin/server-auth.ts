import { createHmac, timingSafeEqual } from "node:crypto";

import { cookies } from "next/headers";

export const ADMIN_SESSION_COOKIE = "dr_prompt_admin_session";

function getAdminKey(): string | null {
  return process.env.ADMIN_API_KEY?.trim() || null;
}

export function getBackendServerUrl(): string {
  return (
    process.env.BACKEND_API_BASE_URL ??
    process.env.NEXT_PUBLIC_API_BASE_URL ??
    "http://localhost:8000"
  ).replace(/\/$/, "");
}

export function requireAdminKey(): string {
  const key = getAdminKey();
  if (!key) throw new Error("ADMIN_API_KEY is not configured for the frontend server.");
  return key;
}

export function adminSessionToken(key = requireAdminKey()): string {
  return createHmac("sha256", key).update("dr-prompt-admin-session-v1").digest("hex");
}

export function adminKeyMatches(candidate: string): boolean {
  const expected = getAdminKey();
  if (!expected) return false;
  const left = Buffer.from(candidate);
  const right = Buffer.from(expected);
  return left.length === right.length && timingSafeEqual(left, right);
}

export async function hasAdminSession(): Promise<boolean> {
  const received = (await cookies()).get(ADMIN_SESSION_COOKIE)?.value;
  if (!received) return false;
  const expected = adminSessionToken();
  const left = Buffer.from(received);
  const right = Buffer.from(expected);
  return left.length === right.length && timingSafeEqual(left, right);
}

export async function adminServerFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${getBackendServerUrl()}/api/v1/admin/${path.replace(/^\//, "")}`, {
    ...init,
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      "X-Admin-Key": requireAdminKey(),
      ...init?.headers,
    },
  });
}

