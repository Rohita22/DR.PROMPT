"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";

import {
  signInWithEmailPassword,
  signUpWithEmailPassword,
  startGoogleSignIn,
} from "@/lib/supabase/auth";
import { createClient } from "@/lib/supabase/client";
import { getSupabasePublicConfig } from "@/lib/supabase/config";

export function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const searchParams = useSearchParams();
  const requestedNext = searchParams.get("next") ?? "/play";
  const next = requestedNext.startsWith("/") && !requestedNext.startsWith("//")
    ? requestedNext
    : "/play";
  const authConfigured = getSupabasePublicConfig() !== null;
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState<"email" | "google" | null>(null);
  const [message, setMessage] = useState<string | null>(
    searchParams.has("auth_error") ? "We couldn’t complete that sign-in. Please try again." : null,
  );

  async function continueWithGoogle() {
    setBusy("google");
    setMessage(null);
    try {
      const callback = new URL("/auth/callback", window.location.origin);
      callback.searchParams.set("next", next);
      await startGoogleSignIn(createClient(), callback.toString());
    } catch {
      setMessage("Google sign-in could not be started. Please try again.");
      setBusy(null);
    }
  }

  async function submitWithEmail(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy("email");
    setMessage(null);
    try {
      if (mode === "login") {
        await signInWithEmailPassword(createClient(), email.trim(), password);
        window.location.assign(next);
        return;
      }
      const callback = new URL("/auth/callback", window.location.origin);
      callback.searchParams.set("next", next);
      const outcome = await signUpWithEmailPassword(
        createClient(),
        email.trim(),
        password,
        callback.toString(),
      );
      if (outcome === "signed_in") {
        window.location.assign(next);
        return;
      }
      setMessage("Your account is ready. Check your email to confirm it, then sign in.");
    } catch {
      setMessage(
        mode === "login"
          ? "We couldn’t sign you in. Check your email and password."
          : "We couldn’t create the account. Check the email and password requirements.",
      );
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="auth-form-wrap">
      <div className="auth-heading-block">
        <span className="section-kicker">{mode === "login" ? "WELCOME BACK" : "CREATE YOUR PLAYER"}</span>
        <h1>{mode === "login" ? "Continue your run." : "Start with level one."}</h1>
        <p>
          {mode === "login"
            ? "Sign in to submit prompts, earn XP, and keep your best scores."
            : "Create a free account to save progress and compete on challenge leaderboards."}
        </p>
      </div>

      <button className="auth-google" disabled={busy !== null || !authConfigured} onClick={() => void continueWithGoogle()}>
        <span>G</span>{busy === "google" ? "Connecting…" : "Continue with Google"}
      </button>
      <div className="auth-page-divider"><span>OR CONTINUE WITH EMAIL</span></div>

      <form className="auth-page-form" onSubmit={(event) => void submitWithEmail(event)}>
        <label htmlFor="email">Email address</label>
        <input id="email" name="email" type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" />
        <div className="auth-label-row"><label htmlFor="password">Password</label><span>Minimum 6 characters</span></div>
        <input id="password" name="password" type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} minLength={6} required value={password} onChange={(event) => setPassword(event.target.value)} placeholder="••••••••" />
        {message !== null ? <div className="auth-message" role="status"><span>i</span><p>{message}</p></div> : null}
        {!authConfigured ? <div className="auth-message" role="alert"><span>!</span><p>Authentication is not configured in this environment.</p></div> : null}
        <button className="auth-submit" disabled={busy !== null || !authConfigured} type="submit">
          {busy === "email" ? "Working…" : mode === "login" ? "Sign in" : "Create account"}<span>→</span>
        </button>
      </form>

      <p className="auth-switch">
        {mode === "login" ? "New to DR. PROMPT?" : "Already have an account?"}{" "}
        <Link href={mode === "login" ? `/signup?next=${encodeURIComponent(next)}` : `/login?next=${encodeURIComponent(next)}`}>
          {mode === "login" ? "Create an account" : "Sign in"}
        </Link>
      </p>
    </div>
  );
}
