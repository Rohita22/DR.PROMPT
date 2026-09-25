import { NextResponse } from "next/server";

import { createClient } from "@/lib/supabase/server";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const requestedNext = url.searchParams.get("next") ?? "/";
  const next = requestedNext.startsWith("/") && !requestedNext.startsWith("//")
    ? requestedNext
    : "/";

  if (code !== null) {
    try {
      const supabase = await createClient();
      const { error } = await supabase.auth.exchangeCodeForSession(code);
      if (error === null) {
        return NextResponse.redirect(new URL(next, url.origin));
      }
    } catch {
      // Redirect with a safe state; no provider or token detail enters the URL.
    }
  }
  return NextResponse.redirect(new URL("/?auth_error=oauth_callback_failed", url.origin));
}
