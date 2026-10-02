import { NextRequest, NextResponse } from "next/server";

import {
  ADMIN_SESSION_COOKIE,
  adminKeyMatches,
  adminSessionToken,
} from "@/lib/admin/server-auth";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const form = await request.formData();
  const candidate = String(form.get("admin_key") ?? "");
  if (!adminKeyMatches(candidate)) {
    return NextResponse.redirect(new URL("/admin/challenges?admin_error=1", request.url), 303);
  }
  const response = NextResponse.redirect(new URL("/admin/challenges", request.url), 303);
  response.cookies.set(ADMIN_SESSION_COOKIE, adminSessionToken(), {
    httpOnly: true,
    sameSite: "strict",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 8,
  });
  return response;
}

export async function DELETE(): Promise<NextResponse> {
  const response = NextResponse.json({ ok: true });
  response.cookies.set(ADMIN_SESSION_COOKIE, "", { httpOnly: true, maxAge: 0, path: "/" });
  return response;
}

