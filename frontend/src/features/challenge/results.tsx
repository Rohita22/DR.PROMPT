import type { RunChallengeResponse, SubmitChallengeResponse } from "@/lib/api/challenges";

function displayValue(value: unknown): string {
  return typeof value === "string" ? value : JSON.stringify(value);
}

export function RunResults({ result }: { result: RunChallengeResponse }) {
  return (
    <section aria-labelledby="run-results-heading" className="result-panel">
      <h2 id="run-results-heading">Run result</h2>
      <p>
        Passed {result.passed}/{result.total} · Accuracy {result.accuracy}%
      </p>
      <div className="test-list">
        {result.tests.map((test) => (
          <article className="test-result" key={test.id}>
            <h3>
              {test.id}: {test.passed ? "PASS" : "FAIL"}
            </h3>
            <dl>
              <dt>Input</dt>
              <dd>{displayValue(test.input)}</dd>
              <dt>Expected</dt>
              <dd>{displayValue(test.expected)}</dd>
              <dt>Actual</dt>
              <dd>{displayValue(test.actual)}</dd>
            </dl>
          </article>
        ))}
      </div>
    </section>
  );
}

export function SubmitResults({ result }: { result: SubmitChallengeResponse }) {
  return (
    <section aria-labelledby="submit-results-heading" className="result-panel">
      <h2 id="submit-results-heading">Submit result</h2>
      <dl className="score-grid">
        <div><dt>Passed</dt><dd>{result.passed}/{result.total}</dd></div>
        <div><dt>Accuracy</dt><dd>{result.accuracy}%</dd></div>
        <div><dt>Prompt tokens</dt><dd>{result.prompt_tokens}</dd></div>
        <div><dt>Efficiency</dt><dd>{result.efficiency}</dd></div>
        <div><dt>Score</dt><dd>{result.score}</dd></div>
        <div><dt>Stars</dt><dd>{result.stars}/3</dd></div>
        <div><dt>XP earned</dt><dd>+{result.xp_earned}</dd></div>
        <div><dt>Total XP</dt><dd>{result.total_xp}</dd></div>
        <div><dt>Best score</dt><dd>{result.best_score}</dd></div>
        <div><dt>Best stars</dt><dd>{result.best_stars}/3</dd></div>
        <div><dt>Completed</dt><dd>{result.completed ? "Yes" : "No"}</dd></div>
      </dl>
    </section>
  );
}
