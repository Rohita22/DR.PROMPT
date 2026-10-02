"use client";

import type { Session } from "@supabase/supabase-js";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  getCurrentUser,
  getCurrentUserProgress,
  getChallengeDetail,
  getChallengeLeaderboard,
  getChallenges,
  getReadableError,
  getApplicationExecutionError,
  getStarterPreviewUrl,
  isApplicationRun,
  isApplicationSubmit,
  runChallenge,
  submitChallenge,
  type CurrentUserResponse,
  type CurrentUserProgressResponse,
  type ChallengeDetailResponse,
  type ChallengeLeaderboardResponse,
  type ChallengeListItem,
  type AnyRunResponse,
  type AnySubmitResponse,
  ApiError,
} from "@/lib/api/challenges";
import { createClient } from "@/lib/supabase/client";
import { getSupabasePublicConfig } from "@/lib/supabase/config";
import {
  signInWithEmailPassword,
  signUpWithEmailPassword,
  startGoogleSignIn,
} from "@/lib/supabase/auth";

import { ApplicationRunResults, ApplicationSubmitResults, StarterPreview } from "./application-results";
import { RunResults, SubmitResults } from "./results";
import { Leaderboard } from "./leaderboard";

export function ChallengeHarness({ backendConnected }: { backendConnected: boolean }) {
  const authConfigured = getSupabasePublicConfig() !== null;
  const [session, setSession] = useState<Session | null>(null);
  const [localUser, setLocalUser] = useState<CurrentUserResponse | null>(null);
  const [progress, setProgress] = useState<CurrentUserProgressResponse | null>(null);
  const [challenges, setChallenges] = useState<ChallengeListItem[]>([]);
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);
  const [challenge, setChallenge] = useState<ChallengeDetailResponse | null>(null);
  const [leaderboard, setLeaderboard] = useState<ChallengeLeaderboardResponse | null>(null);
  const [authReady, setAuthReady] = useState(!authConfigured);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [prompt, setPrompt] = useState(
    "Return exactly YES when the service is currently available, otherwise return exactly NO.",
  );
  const [runResult, setRunResult] = useState<AnyRunResponse | null>(null);
  const [submitResult, setSubmitResult] = useState<AnySubmitResponse | null>(null);
  const [message, setMessage] = useState<string | null>(
    authConfigured ? null : "Supabase browser configuration is unavailable.",
  );
  const [busy, setBusy] = useState<"run" | "submit" | "auth" | null>(null);
  const actionInFlight = useRef(false);
  const submitRetry = useRef<{ prompt: string; key: string } | null>(null);
  const [applicationCooldown, setApplicationCooldown] = useState(false);

  function applyApplicationError(error: unknown, kind: "run" | "submit") {
    setMessage(getApplicationExecutionError(error, kind));
    if (error instanceof ApiError && error.code === "application_rate_limited") {
      setApplicationCooldown(true);
      window.setTimeout(
        () => setApplicationCooldown(false),
        (error.retryAfterSeconds ?? 1) * 1000,
      );
    }
  }

  const estimatedTokens = prompt.trim()
    ? (prompt.match(/[A-Za-z]+|\d+|[^\sA-Za-z\d]/g) ?? []).reduce(
        (total, token) => total + (token.length > 8 ? 2 : 1),
        0,
      )
    : 0;
  const selectedChallenge = challenges.find((item) => item.slug === selectedSlug) ?? null;
  const application = challenge?.challenge_type === "application" ? challenge.application : null;
  const tokenBudget = application !== null ? (challenge?.prompt_token_limit ?? 400) : 120;
  const tokenPercent = Math.min(100, (estimatedTokens / tokenBudget) * 100);
  const starterSrc = challenge !== null ? getStarterPreviewUrl(challenge.slug, application?.starter_preview_viewports[0] ?? "desktop") : "";

  const loadLeaderboard = useCallback(
    async (challengeSlug: string, accessToken: string | null, offset = 0) => {
      const result = await getChallengeLeaderboard(challengeSlug, accessToken, 10, offset);
      setLeaderboard(result);
    },
    [],
  );

  const loadCatalog = useCallback(
    async (accessToken: string | null, preferredSlug: string | null = null) => {
      const catalog = await getChallenges(accessToken);
      setChallenges(catalog.challenges);
      const selected = catalog.challenges.find(
        (item) => item.slug === preferredSlug && item.status !== "locked",
      ) ?? catalog.challenges.find((item) => item.status !== "locked") ?? null;
      setSelectedSlug(selected?.slug ?? null);
      if (selected === null) {
        setChallenge(null);
        setLeaderboard(null);
      } else {
        const detail = await getChallengeDetail(selected.slug, accessToken);
        setChallenge(detail);
        void loadLeaderboard(selected.slug, accessToken).catch(() => {
          setLeaderboard(null);
        });
      }
    },
    [loadLeaderboard],
  );

  useEffect(() => {
    let active = true;
    const currentUrl = new URL(window.location.href);
    const preferredSlug = currentUrl.searchParams.get("challenge");
    if (currentUrl.searchParams.has("auth_error")) {
      currentUrl.searchParams.delete("auth_error");
      window.history.replaceState({}, "", currentUrl);
      queueMicrotask(() => {
        if (active) setMessage("Authentication confirmation could not be completed.");
      });
    }
    if (!authConfigured) {
      queueMicrotask(() => {
        void loadCatalog(null, preferredSlug).catch((error: unknown) => setMessage(getReadableError(error)));
      });
      return;
    }

    // Public challenge content should not wait for an external auth session restore.
    // A signed-in session refreshes the catalog with progression data once available.
    queueMicrotask(() => {
      void loadCatalog(null, preferredSlug).catch((error: unknown) => setMessage(getReadableError(error)));
    });
    const supabase = createClient();

    const applySession = async (nextSession: Session | null) => {
      if (!active) return;
      setSession(nextSession);
      if (nextSession === null) {
        setLocalUser(null);
        setProgress(null);
        try {
          await loadCatalog(null, preferredSlug);
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
          await loadCatalog(nextSession.access_token, preferredSlug);
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
      const accessToken = session?.access_token ?? null;
      const detail = await getChallengeDetail(item.slug, accessToken);
      setChallenge(detail);
      void loadLeaderboard(item.slug, accessToken).catch(() => {
        setLeaderboard(null);
      });
      setRunResult(null);
      setSubmitResult(null);
    } catch (error) {
      setMessage(getReadableError(error));
    }
  }

  async function changeLeaderboardPage(offset: number) {
    if (selectedSlug === null) return;
    setMessage(null);
    try {
      await loadLeaderboard(selectedSlug, session?.access_token ?? null, Math.max(0, offset));
    } catch (error) {
      setMessage(getReadableError(error));
    }
  }

  async function signInWithGoogle() {
    setBusy("auth");
    setMessage(null);
    try {
      await startGoogleSignIn(
        createClient(),
        `${window.location.origin}/auth/callback`,
      );
    } catch {
      setMessage("Unable to start Google sign-in.");
      setBusy(null);
    }
  }

  async function signInWithEmail() {
    setBusy("auth");
    setMessage(null);
    try {
      await signInWithEmailPassword(createClient(), email.trim(), password);
    } catch {
      setMessage("Unable to sign in. Check your email and password.");
    } finally {
      setBusy(null);
    }
  }

  async function createEmailAccount() {
    setBusy("auth");
    setMessage(null);
    try {
      const outcome = await signUpWithEmailPassword(
        createClient(),
        email.trim(),
        password,
        `${window.location.origin}/auth/callback`,
      );
      setMessage(
        outcome === "confirmation_required"
          ? "Account created. Check your email to confirm it, then sign in."
          : "Account created and signed in.",
      );
    } catch {
      setMessage("Unable to create the account. Check the email and password requirements.");
    } finally {
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
    if (selectedSlug === null || actionInFlight.current || applicationCooldown) return;
    actionInFlight.current = true;
    setBusy("run");
    setMessage(null);
    setRunResult(null);
    try {
      setRunResult(await runChallenge(selectedSlug, prompt, session?.access_token ?? null));
    } catch (error) {
      if (application !== null) applyApplicationError(error, "run");
      else setMessage(getReadableError(error));
    } finally {
      actionInFlight.current = false;
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
    if (selectedSlug === null || actionInFlight.current || applicationCooldown) return;
    actionInFlight.current = true;
    setBusy("submit");
    try {
      const idempotencyKey = application !== null
        ? submitRetry.current?.prompt === prompt
          ? submitRetry.current.key
          : crypto.randomUUID()
        : null;
      if (idempotencyKey !== null) submitRetry.current = { prompt, key: idempotencyKey };
      const result = await submitChallenge(
        selectedSlug,
        prompt,
        session.access_token,
        fetch,
        idempotencyKey,
      );
      setSubmitResult(result);
      submitRetry.current = null;
      const [userProgress] = await Promise.all([
        getCurrentUserProgress(session.access_token),
        loadCatalog(session.access_token, selectedSlug),
      ]);
      setProgress(userProgress);
    } catch (error) {
      if (application !== null) applyApplicationError(error, "submit");
      else setMessage(getReadableError(error));
    } finally {
      actionInFlight.current = false;
      setBusy(null);
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-mark" aria-label="Dr. Prompt home">
          <span className="brand-glyph">D</span><span>DR. PROMPT</span>
        </div>
        <span className="topbar-rule" />
        <nav className="breadcrumbs" aria-label="Current challenge">
          <span>{challenge?.track ?? "CONTROL"}</span><span>/</span>
          <span>Level {String(selectedChallenge?.order ?? 1).padStart(2, "0")}</span><span>/</span>
          <strong>{challenge?.title ?? "Loading challenge"}</strong>
        </nav>
        <div className="topbar-status">
          {selectedChallenge?.best_stars ? <div className="best-score">
            <span>Best</span><strong>{selectedChallenge.best_score}</strong>
            <span className="stars">{"★".repeat(selectedChallenge.best_stars)}{"☆".repeat(3 - selectedChallenge.best_stars)}</span>
          </div> : null}
          <span className={`connection ${backendConnected ? "online" : "offline"}`}>
            <i /> Backend: {backendConnected ? "connected" : "unavailable"}
          </span>
        </div>
      </header>

      <div className="workspace-shell">
        <aside className="challenge-brief">
          <section className="level-section" aria-labelledby="path-heading">
            <div className="section-kicker-row">
              <h2 id="path-heading" className="section-kicker">CHALLENGE PATH</h2>
              <span>{challenges.length} levels</span>
            </div>
            <div className="level-list">
              {challenges.map((item) => <button
                className="level-card" key={item.slug}
                disabled={item.status === "locked" || busy !== null}
                onClick={() => void selectChallenge(item)} aria-pressed={selectedSlug === item.slug}
              >
                <span className="level-number">{String(item.order).padStart(2, "0")}</span>
                <span className="level-copy"><strong>{item.title}</strong><small>{item.difficulty} · {item.challenge_type === "application" ? "coding agent · " : ""}{item.status}</small></span>
                <span className="level-stars">{item.status === "locked" ? "LOCKED" : item.best_stars > 0 ? `${item.best_stars}/3 ★` : "OPEN"}</span>
              </button>)}
            </div>
          </section>

          {challenge !== null ? <div className="brief-content">
            <div className="challenge-heading">
              <div className="badge-row">
                <span className="badge badge-primary">LEVEL {String(challenge.order).padStart(2, "0")}</span>
                <span className="badge">{challenge.track}</span><span className="badge badge-success">{challenge.difficulty}</span>
                {application !== null ? <span className="badge">coding agent</span> : null}
              </div>
              <h1>{challenge.title}</h1><p>{challenge.description}</p>
            </div>
            <section className="brief-section"><h2 className="section-kicker">OBJECTIVE</h2><p className="objective">{challenge.objective}</p></section>
            <section className="brief-section">
              <h2 className="section-kicker">{application !== null ? "REQUIREMENTS" : "CONSTRAINTS"}</h2>
              <ol className="constraint-list">{challenge.constraints.map((constraint, index) => <li key={constraint}><span>{String(index + 1).padStart(2, "0")}</span>{constraint}</li>)}</ol>
            </section>
            {application !== null ? <StarterPreview src={application.available === false ? "" : starterSrc} title={challenge.title} files={application.editable_files} /> : <section className="brief-section">
              <h2 className="section-kicker">EXAMPLES</h2>
              <div className="example-list">{challenge.examples.map((example, index) => <article key={index}>
                <code>{String(example.input)}</code><div><span>→</span><strong>{String(example.expected)}</strong></div>
              </article>)}</div>
            </section>}
          </div> : <div className="brief-skeleton">Loading challenge brief…</div>}

          <details className="account-drawer" open={!authConfigured || session === null}>
            <summary><span><span className="avatar">{session?.user.email?.[0]?.toUpperCase() ?? "?"}</span> Account</span><span className="account-status">{session ? "SIGNED IN" : "GUEST"}</span></summary>
            <div className="account-body">
              {!authReady ? <p>Restoring session…</p> : session === null ? <div className="auth-options">
                <button className="google-button" disabled={busy !== null || !authConfigured} onClick={() => void signInWithGoogle()}>Sign in with Google</button>
                <div className="auth-divider"><span>or use email</span></div>
                <form onSubmit={(event) => { event.preventDefault(); void signInWithEmail(); }}>
                  <label htmlFor="auth-email">Email</label>
                  <input id="auth-email" type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" />
                  <label htmlFor="auth-password">Password</label>
                  <input id="auth-password" type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} placeholder="••••••••" />
                  <div className="auth-actions"><button className="primary-light" disabled={busy !== null || !authConfigured} type="submit">Sign in</button><button className="text-button" disabled={busy !== null || !authConfigured} type="button" onClick={() => void createEmailAccount()}>Create account</button></div>
                </form>
              </div> : <div className="signed-in-card">
                <div><strong>{session.user.email ?? "Signed-in player"}</strong><small>{localUser?.id ?? "Synchronizing profile…"}</small></div>
                <button className="text-button" disabled={busy !== null} onClick={() => void signOut()}>Sign out</button>
              </div>}
            </div>
          </details>

          {session !== null && progress !== null ? <section className="progress-card" aria-labelledby="progress-heading">
            <h2 id="progress-heading" className="section-kicker">YOUR PROGRESS</h2>
            <dl><div><dt>Total XP</dt><dd>{progress.total_xp}</dd></div><div><dt>Completed</dt><dd>{progress.challenges_completed}</dd></div><div><dt>Stars</dt><dd>{progress.stars_earned}</dd></div></dl>
          </section> : null}
        </aside>

        <main className="prompt-workspace">
          <div className="workspace-heading"><div><span className="workspace-kicker">{application !== null ? "AGENT WORKSPACE" : "PROMPT WORKSPACE"}</span><h2>{application !== null ? "Instruct the coding agent." : "Build, test, improve."}</h2></div><span className="model-pill">openai/gpt-oss-20b</span></div>
          <section className="editor-card" aria-labelledby="prompt-label">
            <div className="editor-toolbar"><label id="prompt-label" htmlFor="prompt">PROMPT</label><div className="token-meter" aria-label={`${estimatedTokens} of ${tokenBudget} estimated tokens`}><span><i style={{ width: `${tokenPercent}%` }} /></span><strong>{estimatedTokens} / {tokenBudget} tokens</strong></div></div>
            <textarea id="prompt" rows={10} value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder={application !== null ? "Tell the coding agent exactly what to change. It sees only your prompt and the editable files." : "Write instructions for the model. Each test input is sent after your prompt."} spellCheck={false} />
            <div className="editor-footer">{application !== null ? <><span>{prompt.length} chars</span><span>edits {application.editable_files.join(" · ")}</span><span>whole-file edits</span></> : <><span>{prompt.length} chars</span><span>temperature 0</span><span>8 output tokens</span></>}</div>
          </section>
          <div className="action-row">
            {application?.available === false ? <p className="sandbox-notice" role="status">Executable challenges aren’t available on this server right now.</p> : null}
            <div className="action-group"><button className="run-button" disabled={busy !== null || applicationCooldown || application?.available === false || !prompt.trim()} onClick={() => void run()}>{busy === "run" ? <><span className="spinner" /> {application !== null ? "Agent working…" : "Running…"}</> : <>Run <kbd>⌘↵</kbd></>}</button><span>{application !== null ? "Agent edits a fresh copy" : "Debug on visible tests"}<br /><small>{application !== null ? "Visible checks · not scored" : "Not scored"}</small></span></div>
            <div className="action-group submit-group"><span>{application !== null ? "Judge on hidden checks" : "Judge on hidden tests"}<br /><small>Counts toward your score</small></span><button className="submit-button" disabled={busy !== null || applicationCooldown || application?.available === false || !prompt.trim()} onClick={() => void submit()}>{busy === "submit" ? <><span className="spinner" /> {application !== null ? "Agent working…" : "Submitting…"}</> : <>Submit <kbd>⌘⇧↵</kbd></>}</button></div>
          </div>
          {message !== null ? <div className="system-message" role="alert"><span>SYSTEM</span><p>{message}</p></div> : null}
          <section className="results-area" aria-label="Evaluation results">
            {runResult === null && submitResult === null ? <div className="empty-results"><span className="empty-icon">›_</span><strong>Ready when you are.</strong><p>{application !== null ? "Run your prompt to see what the coding agent builds: screenshots of the result, visible checks, the build, and the files it changed." : "Run your prompt to inspect visible test inputs, expected answers, and model outputs."}</p></div> : null}
            {runResult !== null ? isApplicationRun(runResult) ? <ApplicationRunResults result={runResult} starterSrc={starterSrc} /> : <RunResults result={runResult} /> : null}
            {submitResult !== null ? isApplicationSubmit(submitResult) ? <ApplicationSubmitResults result={submitResult} /> : <SubmitResults result={submitResult} /> : null}
          </section>
          {leaderboard !== null ? <Leaderboard result={leaderboard} onPrevious={() => void changeLeaderboardPage(leaderboard.offset - leaderboard.limit)} onNext={() => void changeLeaderboardPage(leaderboard.offset + leaderboard.limit)} /> : null}
        </main>
      </div>
    </div>
  );
}
