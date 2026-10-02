import Link from "next/link";

import type { CurrentUserProfileResponse } from "@/lib/api/challenges";

function formatSubmittedAt(value: string): string {
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(new Date(value));
}

export function ProfileLoading() {
  return (
    <main className="profile-page" aria-busy="true" aria-live="polite">
      <div className="profile-loading-head"><span className="profile-skeleton profile-skeleton-avatar" /><div><span className="profile-skeleton profile-skeleton-short" /><span className="profile-skeleton profile-skeleton-title" /></div></div>
      <div className="profile-loading-grid">{Array.from({ length: 4 }, (_, index) => <span className="profile-skeleton" key={index} />)}</div>
      <span className="sr-only">Loading your profile</span>
    </main>
  );
}

export function ProfileError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <main className="account-state" role="alert">
      <span className="result-tag profile-system-tag">SYSTEM</span>
      <h1>We couldn’t load your profile.</h1>
      <p>{message}</p>
      <button className="site-cta profile-retry" onClick={onRetry}>Try again <span>→</span></button>
    </main>
  );
}

export function ProfileSummary({
  profile,
  onSignOut,
}: {
  profile: CurrentUserProfileResponse;
  onSignOut: () => void;
}) {
  const levelPercent = Math.min(
    100,
    Math.max(0, (profile.level_progress.earned_in_level / profile.level_progress.required_in_level) * 100),
  );
  const initials = profile.player.replace("Player-", "").slice(0, 2).toUpperCase();

  return (
    <main className="profile-page">
      <header className="profile-hero">
        <div className="account-identity">
          <span className="account-avatar" aria-hidden="true">{initials}</span>
          <div><span className="section-kicker">PLAYER PROFILE</span><h1>{profile.player}</h1><p>Level {profile.level} · {profile.total_xp} total XP</p></div>
        </div>
        <button className="account-signout" onClick={onSignOut}>Sign out</button>
      </header>

      <section className="profile-level" aria-labelledby="level-progress-heading">
        <div><span className="section-kicker">LEVEL PROGRESS</span><h2 id="level-progress-heading">Level {profile.level}</h2></div>
        <div className="profile-level-meter">
          <div><span>{profile.level_progress.earned_in_level} XP earned</span><span>{profile.level_progress.required_in_level} XP to advance</span></div>
          <span className="profile-progress-track" role="progressbar" aria-label={`Progress through level ${profile.level}`} aria-valuemin={0} aria-valuemax={profile.level_progress.required_in_level} aria-valuenow={profile.level_progress.earned_in_level}><i style={{ width: `${levelPercent}%` }} /></span>
          <small>{profile.total_xp} total XP · Level {profile.level + 1} at {profile.level_progress.next_level_at} XP</small>
        </div>
      </section>

      <section className="profile-stat-grid" aria-label="Player statistics">
        <article><span>CHALLENGES</span><strong>{profile.challenges.completed}<i> / {profile.challenges.total}</i></strong><small>published challenges completed</small></article>
        <article><span>STARS EARNED</span><strong>{profile.stars.earned}<i> / {profile.stars.total}</i></strong><small>best stars across challenges</small></article>
        <article><span>PERFECT CLEARS</span><strong>{profile.three_star_completions}</strong><small>three-star completions</small></article>
        <article><span>BEST POSITION</span><strong>{profile.best_leaderboard_position === null ? "—" : `#${profile.best_leaderboard_position}`}</strong><small>across active leaderboards</small></article>
      </section>

      <section className="profile-activity" aria-labelledby="recent-activity-heading">
        <div className="account-section-heading"><div><span className="section-kicker">LATEST RUNS</span><h2 id="recent-activity-heading">Recent challenge activity</h2></div><Link href="/play">Open workspace →</Link></div>
        {profile.recent_activity.length === 0 ? (
          <div className="profile-empty"><span>01</span><h3>Your first score starts here.</h3><p>Complete a hidden-test submission to begin building your profile, earning stars, and climbing challenge leaderboards.</p><Link className="site-cta" href="/play">Play the first challenge <span>→</span></Link></div>
        ) : (
          <div className="activity-list">
            {profile.recent_activity.map((activity, index) => (
              <article className="activity-row" key={`${activity.challenge}-${activity.submitted_at}-${index}`}>
                <span className="activity-index">{String(index + 1).padStart(2, "0")}</span>
                <div className="activity-title"><strong>{activity.title}</strong><span>{formatSubmittedAt(activity.submitted_at)}</span></div>
                <div className="activity-metric"><span>SCORE</span><strong>{activity.score}</strong></div>
                <div className="activity-metric"><span>ACCURACY</span><strong>{activity.accuracy}%</strong></div>
                <div className="activity-stars" aria-label={`${activity.stars} of 3 stars`}>{"★".repeat(activity.stars)}<i>{"★".repeat(3 - activity.stars)}</i></div>
                <div className="activity-xp"><strong>+{activity.xp_earned}</strong><span>XP</span></div>
                <Link className="progress-action" href={`/play?challenge=${encodeURIComponent(activity.challenge)}`}>Replay →</Link>
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
