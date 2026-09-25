"use client";

import type { Session } from "@supabase/supabase-js";
import { useCallback, useEffect, useState } from "react";

import {
  getCurrentUser,
  getCurrentUserProgress,
  getChallengeDetail,
  getChallenges,
  getReadableError,
  runChallenge,
  submitChallenge,
  type CurrentUserResponse,
  type CurrentUserProgressResponse,
  type ChallengeDetailResponse,
  type ChallengeListItem,
  type RunChallengeResponse,
  type SubmitChallengeResponse,
} from "@/lib/api/challenges";
import { createClient } from "@/lib/supabase/client";
import { getSupabasePublicConfig } from "@/lib/supabase/config";

import { RunResults, SubmitResults } from "./results";

type OAuthProvider = "google" | "github";

export function ChallengeHarness({ backendConnected }: { backendConnected: boolean }) {
  const authConfigured = getSupabasePublicConfig() !== null;
  const [session, setSession] = useState<Session | null>(null);
  const [localUser, setLocalUser] = useState<CurrentUserResponse | null>(null);
  const [progress, setProgress] = useState<CurrentUserProgressResponse | null>(null);
  const [challenges, setChallenges] = useState<ChallengeListItem[]>([]);
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);
  const [challenge, setChallenge] = useState<ChallengeDetailResponse | null>(null);
  const [authReady, setAuthReady] = useState(!authConfigured);
  const [prompt, setPrompt] = useState(
    "Return exactly YES when the service is currently available, otherwise return exactly NO.",
  );
  const [runResult, setRunResult] = useState<RunChallengeResponse | null>(null);
  const [submitResult, setSubmitResult] = useState<SubmitChallengeResponse | null>(null);
  const [message, setMessage] = useState<string | null>(
    authConfigured ? null : "Supabase browser configuration is unavailable.",
  );
  const [busy, setBusy] = useState<"run" | "submit" | "auth" | null>(null);

  const loadCatalog = useCallback(
    async (accessToken: string | null, preferredSlug: string | null = null) => {
      const catalog = await getChallenges(accessToken);
      setChallenges(catalog.challenges);
      const selected = catalog.challenges.find(
        (item) => item.slug === preferredSlug && item.status !== "locked",
      ) ?? catalog.challenges.find((item) => item.status !== "locked") ?? null;
      setSelectedSlug(selected?.slug ?? null);
      setChallenge(
        selected === null ? null : await getChallengeDetail(selected.slug, accessToken),
      );
    },
    [],
  );

  useEffect(() => {
    let active = true;
    const currentUrl = new URL(window.location.href);
    if (currentUrl.searchParams.has("auth_error")) {
      currentUrl.searchParams.delete("auth_error");
      window.history.replaceState({}, "", currentUrl);
      queueMicrotask(() => {
        if (active) setMessage("OAuth sign-in could not be completed.");
      });
    }
    if (!authConfigured) {
      queueMicrotask(() => {
        void loadCatalog(null).catch((error: unknown) => setMessage(getReadableError(error)));
      });
      return;
    }
    const supabase = createClient();

    const applySession = async (nextSession: Session | null) => {
      if (!active) return;
      setSession(nextSession);
      if (nextSession === null) {
        setLocalUser(null);
        setProgress(null);
        try {
          await loadCatalog(null);
        } catch (error) {
          if (active) setMessage(getReadableError(error));
        } finally {
          if (active) setAuthReady(true);
        }
        return;
      }
      try {
        const [user, userProgress] = await Promise.all([
          getCurrentUser(nextSession.access_token),
          getCurrentUserProgress(nextSession.access_token),
        ]);
        if (active) {
          setLocalUser(user);
          setProgress(userProgress);
          await loadCatalog(nextSession.access_token);
        }
      } catch (error) {
        if (active) setMessage(getReadableError(error));
      } finally {
        if (active) setAuthReady(true);
      }
    };

    void supabase.auth.getSession().then(({ data }) => applySession(data.session));
    const { data } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      void applySession(nextSession);
    });
    return () => {
      active = false;
      data.subscription.unsubscribe();
    };
  }, [authConfigured, loadCatalog]);

  async function selectChallenge(item: ChallengeListItem) {
    if (item.status === "locked") return;
    setMessage(null);
    try {
      setSelectedSlug(item.slug);
      setChallenge(await getChallengeDetail(item.slug, session?.access_token ?? null));
      setRunResult(null);
      setSubmitResult(null);
    } catch (error) {
      setMessage(getReadableError(error));
    }
  }

  async function signIn(provider: OAuthProvider) {
    setBusy("auth");
    setMessage(null);
    try {
      const supabase = createClient();
      const { error } = await supabase.auth.signInWithOAuth({
        provider,
        options: { redirectTo: `${window.location.origin}/auth/callback` },
      });
      if (error !== null) throw error;
    } catch {
      setMessage("Unable to start OAuth sign-in.");
      setBusy(null);
    }
  }

  async function signOut() {
    setBusy("auth");
    setMessage(null);
    try {
      await createClient().auth.signOut();
      setSession(null);
      setLocalUser(null);
      setProgress(null);
    } catch {
      setMessage("Unable to sign out.");
    } finally {
      setBusy(null);
    }
  }

  async function run() {
    if (selectedSlug === null) return;
    setBusy("run");
    setMessage(null);
    setRunResult(null);
    try {
      setRunResult(await runChallenge(selectedSlug, prompt));
    } catch (error) {
      setMessage(getReadableError(error));
    } finally {
      setBusy(null);
    }
  }

  async function submit() {
    setMessage(null);
    setSubmitResult(null);
    if (session === null) {
      setMessage("Sign in before submitting a challenge.");
      return;
    }
    if (selectedSlug === null) return;
    setBusy("submit");
    try {
      const result = await submitChallenge(selectedSlug, prompt, session.access_token);
      setSubmitResult(result);
      const [userProgress] = await Promise.all([
        getCurrentUserProgress(session.access_token),
        loadCatalog(session.access_token, selectedSlug),
      ]);
      setProgress(userProgress);
    } catch (error) {
      setMessage(getReadableError(error));
    } finally {
      setBusy(null);
    }
  }

  return (
    <main className="harness">
      <header>
        <p className="eyebrow">TEMPORARY DEVELOPMENT HARNESS</p>
        <h1>DR. PROMPT</h1>
        <p>Backend: {backendConnected ? "connected" : "unavailable"}</p>
      </header>

      <section className="panel" aria-labelledby="auth-heading">
        <h2 id="auth-heading">Authentication</h2>
        {!authReady ? <p>Restoring session…</p> : session === null ? (
          <div className="button-row">
            <button disabled={busy !== null} onClick={() => void signIn("google")}>
              Sign in with Google
            </button>
            <button disabled={busy !== null} onClick={() => void signIn("github")}>
              Sign in with GitHub
            </button>
          </div>
        ) : (
          <div>
            <p>Supabase identity: {session.user.email ?? session.user.id}</p>
            <p>Local user: {localUser?.id ?? "synchronizing…"}</p>
            <button disabled={busy !== null} onClick={() => void signOut()}>Sign Out</button>
          </div>
        )}
      </section>

      <section className="panel" aria-labelledby="path-heading">
        <h2 id="path-heading">CONTROL challenge path</h2>
        <div className="test-list">
          {challenges.map((item) => (
            <button
              key={item.slug}
              disabled={item.status === "locked" || busy !== null}
              onClick={() => void selectChallenge(item)}
              aria-pressed={selectedSlug === item.slug}
            >
              {item.order}. {item.title} · {item.difficulty} · {item.status}
              {item.best_stars > 0 ? ` · ${item.best_stars}/3 stars` : ""}
            </button>
          ))}
        </div>
      </section>

      {challenge !== null ? <section className="panel" aria-labelledby="challenge-heading">
        <p className="eyebrow">{challenge.track} · {challenge.difficulty}</p>
        <h2 id="challenge-heading">{challenge.title}</h2>
        <p>{challenge.description}</p>
        <p><strong>Objective:</strong> {challenge.objective}</p>
        <ul>{challenge.constraints.map((constraint) => <li key={constraint}>{constraint}</li>)}</ul>
        <h3>Examples</h3>
        <ul>
          {challenge.examples.map((example, index) => (
            <li key={index}>{String(example.input)} → {String(example.expected)}</li>
          ))}
        </ul>
        <label htmlFor="prompt">Player prompt</label>
        <textarea
          id="prompt"
          rows={8}
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
        />
        <div className="button-row">
          <button disabled={busy !== null || !prompt.trim()} onClick={() => void run()}>
            {busy === "run" ? "Running…" : "Run visible tests"}
          </button>
          <button disabled={busy !== null || !prompt.trim()} onClick={() => void submit()}>
            {busy === "submit" ? "Submitting…" : "Submit hidden tests"}
          </button>
        </div>
      </section> : null}

      {session !== null && progress !== null ? (
        <section className="panel" aria-labelledby="progress-heading">
          <h2 id="progress-heading">Current user progress</h2>
          <dl className="score-grid">
            <div><dt>Total XP</dt><dd>{progress.total_xp}</dd></div>
            <div><dt>Challenges completed</dt><dd>{progress.challenges_completed}</dd></div>
            <div><dt>Stars earned</dt><dd>{progress.stars_earned}</dd></div>
            {progress.challenges.map((item) => (
              <div key={item.challenge}>
                <dt>{item.challenge}</dt>
                <dd>{item.attempts} attempts · best {item.best_score} · {item.best_stars}/3 stars</dd>
              </div>
            ))}
          </dl>
        </section>
      ) : null}

      {message !== null ? <p className="error" role="alert">{message}</p> : null}
      {runResult !== null ? <RunResults result={runResult} /> : null}
      {submitResult !== null ? <SubmitResults result={submitResult} /> : null}
    </main>
  );
}
