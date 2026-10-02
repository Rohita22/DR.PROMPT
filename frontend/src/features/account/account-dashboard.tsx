"use client";

import type { Session } from "@supabase/supabase-js";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  getChallenges,
  getCurrentUser,
  getCurrentUserProgress,
  getReadableError,
  type ChallengeListItem,
  type CurrentUserProgressResponse,
  type CurrentUserResponse,
} from "@/lib/api/challenges";
import { createClient } from "@/lib/supabase/client";
import { getSupabasePublicConfig } from "@/lib/supabase/config";

export function AccountDashboard() {
  const router = useRouter();
  const [session, setSession] = useState<Session | null>(null);
  const [user, setUser] = useState<CurrentUserResponse | null>(null);
  const [progress, setProgress] = useState<CurrentUserProgressResponse | null>(null);
  const [challenges, setChallenges] = useState<ChallengeListItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (getSupabasePublicConfig() === null) {
      queueMicrotask(() => setError("Authentication is not configured in this environment."));
      return;
    }
    let active = true;
    const supabase = createClient();
    void supabase.auth.getSession().then(async ({ data }) => {
      if (!active) return;
      if (data.session === null) {
        router.replace("/login?next=/account");
        return;
      }
      setSession(data.session);
      try {
        const [nextUser, nextProgress, catalog] = await Promise.all([
          getCurrentUser(data.session.access_token),
          getCurrentUserProgress(data.session.access_token),
          getChallenges(data.session.access_token),
        ]);
        if (active) {
          setUser(nextUser);
          setProgress(nextProgress);
          setChallenges(catalog.challenges);
        }
      } catch (loadError) {
        if (active) setError(getReadableError(loadError));
      }
    });
    return () => { active = false; };
  }, [router]);

  async function signOut() {
    if (session === null) return;
    await createClient().auth.signOut();
    router.push("/");
    router.refresh();
  }

  if (error !== null) {
    return <div className="account-state"><span className="result-tag">SYSTEM</span><h1>We couldn’t load your progress.</h1><p>{error}</p><Link className="site-cta" href="/play">Open the workspace</Link></div>;
  }
  if (user === null || progress === null) {
    return <div className="account-state"><span className="spinner" /><h1>Loading your player profile…</h1><p>Syncing challenge progress and best scores.</p></div>;
  }

  const initials = (user.email ?? user.id).slice(0, 2).toUpperCase();
  return (
    <main className="account-page">
      <header className="account-hero">
        <div className="account-identity"><span className="account-avatar">{initials}</span><div><span className="section-kicker">PLAYER PROFILE</span><h1>{user.username ?? user.email ?? "Prompt player"}</h1><p>{progress.challenges_completed === 0 ? "Your first challenge is ready." : `${progress.challenges_completed} challenge${progress.challenges_completed === 1 ? "" : "s"} completed.`}</p></div></div>
        <button className="account-signout" onClick={() => void signOut()}>Sign out</button>
      </header>

      <section className="account-stat-grid" aria-label="Player statistics">
        <article><span>TOTAL XP</span><strong>{progress.total_xp}</strong><small>earned from milestones</small></article>
        <article><span>CHALLENGES</span><strong>{progress.challenges_completed}<i> / {challenges.length}</i></strong><small>completed in CONTROL</small></article>
        <article><span>STARS</span><strong>{progress.stars_earned}<i> / {challenges.length * 3}</i></strong><small>across every level</small></article>
      </section>

      <section className="account-content">
        <div className="account-section-heading"><div><span className="section-kicker">CONTROL TRACK</span><h2>Your challenge path</h2></div><Link href="/play">Open workspace →</Link></div>
        <div className="progress-list">
          {challenges.map((challenge) => {
            const itemProgress = progress.challenges.find((item) => item.challenge === challenge.slug);
            return <article className={`progress-row progress-${challenge.status}`} key={challenge.slug}>
              <span className="progress-index">{String(challenge.order).padStart(2, "0")}</span>
              <div className="progress-title"><strong>{challenge.title}</strong><span>{challenge.difficulty} · {challenge.status}</span></div>
              <div className="progress-score"><span>BEST SCORE</span><strong>{itemProgress?.best_score ?? "—"}</strong></div>
              <div className="progress-score"><span>ATTEMPTS</span><strong>{itemProgress?.attempts ?? 0}</strong></div>
              <div className="progress-stars">{"★".repeat(itemProgress?.best_stars ?? 0)}<i>{"★".repeat(3 - (itemProgress?.best_stars ?? 0))}</i></div>
              {challenge.status === "locked" ? <span className="progress-action locked">LOCKED</span> : <Link className="progress-action" href={`/play?challenge=${encodeURIComponent(challenge.slug)}`}>{challenge.completed ? "Replay" : "Play"} →</Link>}
            </article>;
          })}
        </div>
      </section>
    </main>
  );
}
