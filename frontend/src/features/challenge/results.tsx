import type { RunChallengeResponse, SubmitChallengeResponse } from "@/lib/api/challenges";

function displayValue(value: unknown): string {
  return typeof value === "string" ? value : JSON.stringify(value);
}

export function RunResults({ result }: { result: RunChallengeResponse }) {
  return (
    <section aria-labelledby="run-results-heading" className="result-panel run-results">
      <div className="result-heading"><span className="result-tag">RUN</span><h2 id="run-results-heading">{result.passed} / {result.total} visible passing</h2><span>Accuracy {result.accuracy}% · debug only</span></div>
      <div className="test-list">
        {result.tests.map((test) => (
          <article className={`test-result ${test.passed ? "passed" : "failed"}`} key={test.id}>
            <header><span className="status-tag">{test.passed ? "PASS" : "FAIL"}</span><h3>{test.id}</h3>{!test.passed && test.failure_reason ? <code>{test.failure_reason}</code> : null}</header>
            <div className="test-grid"><div className="test-input"><span>Input</span><code>{displayValue(test.input)}</code></div><div><span>Expected</span><code>{displayValue(test.expected)}</code></div><div><span>Actual</span><code>{displayValue(test.actual)}</code></div></div>
          </article>
        ))}
      </div>
    </section>
  );
}

export function SubmitResults({ result }: { result: SubmitChallengeResponse }) {
  return (
    <section aria-labelledby="submit-results-heading" className="result-panel submit-results">
      <div className="result-heading"><span className="result-tag submit-tag">SUBMIT</span><h2 id="submit-results-heading">Hidden evaluation complete</h2><span>Exact output · v{result.version}</span></div>
      <div className="score-hero"><div><span>Final score</span><strong>{result.score}</strong><small>/ 100</small></div><div className="score-stars" aria-label={`${result.stars} of 3 stars`}>{"★".repeat(result.stars)}<i>{"★".repeat(3 - result.stars)}</i></div></div>
      <dl className="score-grid">
        <div><dt>Hidden tests</dt><dd>{result.passed} / {result.total}</dd><small>passed</small></div>
        <div><dt>Accuracy</dt><dd>{result.accuracy}%</dd><small>80% of score</small></div>
        <div><dt>Efficiency</dt><dd>{result.efficiency}%</dd><small>{result.prompt_tokens} tokens</small></div>
        <div><dt>Stars</dt><dd>{result.stars}/3</dd><small>this submit</small></div>
        <div><dt>XP earned</dt><dd>+{result.xp_earned}</dd><small>{result.total_xp} Total XP</small></div>
        <div><dt>Best score</dt><dd>{result.best_score}</dd><small>{result.best_stars}/3 best stars</small></div>
      </dl>
      <p className="completion-note"><span>NEXT</span>{result.completed ? "Challenge complete. Refine the prompt to improve your score or select the next unlocked level." : "Keep iterating—the challenge completes once your prompt meets the target."}</p>
    </section>
  );
}
