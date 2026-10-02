import type { ChallengeLeaderboardResponse } from "@/lib/api/challenges";

export function Leaderboard({
  result,
  onPrevious,
  onNext,
}: {
  result: ChallengeLeaderboardResponse;
  onPrevious: () => void;
  onNext: () => void;
}) {
  return (
    <section className="leaderboard-panel" aria-labelledby="leaderboard-heading">
      <div className="leaderboard-heading"><div><span className="workspace-kicker">COMMUNITY</span><h2 id="leaderboard-heading">Leaderboard</h2></div><p>Best submission per player · {result.total_entries} players</p></div>
      {result.entries.length === 0 ? (
        <p>No qualifying submissions yet.</p>
      ) : (
          <table className="leaderboard-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Player</th>
                <th>Score</th>
                <th>Accuracy</th>
                <th>Tokens</th>
                <th>Stars</th>
              </tr>
            </thead>
            <tbody>
              {result.entries.map((entry) => (
                <tr
                  key={entry.rank}
                  className={entry.is_current_user ? "current-player" : undefined}
                >
                  <td className="rank-cell">{String(entry.rank).padStart(2, "0")}</td>
                  <td>{entry.player}</td>
                  <td>{entry.score}</td>
                  <td>{entry.accuracy}%</td>
                  <td>{entry.prompt_tokens}</td>
                  <td className="table-stars">{"★".repeat(entry.stars)}{"☆".repeat(3 - entry.stars)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      {result.current_user_entry !== null
      && !result.entries.some((entry) => entry.is_current_user) ? (
        <p className="current-player-summary">
          Your position: #{result.current_user_entry.rank} · {result.current_user_entry.score} points
        </p>
      ) : null}
      <div className="pagination">
        <button disabled={result.offset === 0} onClick={onPrevious}>
          Previous
        </button>
        <button disabled={!result.has_more} onClick={onNext}>
          Next
        </button>
      </div>
    </section>
  );
}
