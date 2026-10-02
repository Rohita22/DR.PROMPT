/* eslint-disable @next/next/no-img-element -- screenshots are runtime data URIs and backend PNGs. */
import type {
  ApplicationRunResponse,
  ApplicationSubmitResponse,
} from "@/lib/api/challenges";

function Shot({
  title,
  viewport,
  src,
  alt,
  empty,
  tone,
}: {
  title: string;
  viewport: string;
  src: string | null;
  alt: string;
  empty?: string;
  tone?: "result" | "phone";
}) {
  return (
    <figure className={`shot-frame${tone ? ` ${tone}` : ""}`}>
      <figcaption><span>{title}</span><small>{viewport}</small></figcaption>
      {src !== null ? <img src={src} alt={alt} loading="lazy" /> : <div className="shot-empty">{empty}</div>}
    </figure>
  );
}

function emptyReason(result: ApplicationRunResponse): string {
  if (result.agent.status === "rejected") return "Nothing was built because the agent’s edits were rejected.";
  if (result.build.status === "failed") return "Nothing rendered because the build failed.";
  return "No render is available for this run.";
}

export function StarterPreview({ src, files, title = "Application", label = "Starter" }: { src: string; files: string[]; title?: string; label?: string }) {
  return (
    <>
      <section className="brief-section">
        <h2 className="section-kicker">STARTER APP</h2>
        <figure className="starter-preview">
          {src ? <img src={src} alt={`${title} starter before any changes`} loading="lazy" /> : <div className="shot-empty">App preview becomes available when executable challenges are enabled.</div>}
          <figcaption>{label} · Before your instructions</figcaption>
        </figure>
      </section>
      <section className="brief-section">
        <h2 className="section-kicker">THE AGENT CAN EDIT</h2>
        <div className="file-chips">{files.map((file) => <code key={file}>{file}</code>)}</div>
        <p className="brief-note">Your prompt is the agent’s only instruction. It never sees the requirements above unless you tell it.</p>
      </section>
    </>
  );
}

export function ApplicationRunResults({
  result,
  starterSrc,
}: {
  result: ApplicationRunResponse;
  starterSrc?: string;
}) {
  const [primary, ...additional] = result.screenshots;
  return (
    <section aria-labelledby="app-run-heading" className="result-panel app-results">
      <div className="result-heading">
        <span className="result-tag">RUN</span>
        <h2 id="app-run-heading">This is what your instructions made the AI build.</h2>
        <span>{result.passed} / {result.total} visible checks · {result.evaluation_score}% · not scored</span>
      </div>

      {result.agent.status === "rejected" ? (
        <div className="agent-alert" role="status">
          <span>AGENT</span>
          <p>{result.agent.message} Rewrite your prompt so the agent returns edits to the allowed files.</p>
        </div>
      ) : null}

      <div className={starterSrc ? "comparison-grid" : "result-gallery"}>
        {starterSrc ? <Shot title="STARTER" viewport={primary ? `${primary.width}px · ${primary.label ?? primary.viewport}` : "Original"} src={starterSrc} alt="Starter page before the coding agent's changes." /> : null}
        <Shot title="YOUR AI’S RESULT" viewport={primary ? `${primary.width}px · ${primary.label ?? primary.viewport}` : "Result"} src={primary?.image ?? null} alt="The page after the coding agent applied your instructions." empty={emptyReason(result)} tone="result" />
      </div>
      <div className={`app-detail-grid${additional.length === 0 ? " no-phone" : ""}`}>
        {additional.length ? <div className="result-gallery">{additional.map((shot) => <Shot key={shot.viewport} title={shot.label ?? shot.viewport} viewport={`${shot.width}px`} src={shot.image} alt={`Coding agent result · ${shot.label ?? shot.viewport}`} tone={shot.width < 600 ? "phone" : "result"} />)}</div> : null}
        <div className="app-detail-stack">
          <div className="check-list" aria-label="Visible checks">
            {result.checks.map((check) => (
              <article className={`check-row ${check.passed ? "passed" : "failed"}`} key={check.id}>
                <span className="status-tag">{check.passed ? "PASS" : "FAIL"}</span>
                <div><strong>{check.label}</strong>{!check.passed && check.message ? <p>{check.message}</p> : null}</div>
              </article>
            ))}
          </div>
          <div className="app-meta-grid">
            <section className="meta-card" aria-label="Build">
              <h3>Build</h3>
              <span className={`build-pill ${result.build.status}`}>{result.build.status}</span>
              {result.build.log ? <pre>{result.build.log}</pre> : null}
            </section>
            <section className="meta-card" aria-label="Changed files">
              <h3>Changed files</h3>
              {result.changed_files.length > 0 ? (
                <ul className="changed-list">
                  {result.changed_files.map((file) => (
                    <li key={file.path}><code>{file.path}</code><span className="diff-add">+{file.additions}</span><span className="diff-del">−{file.deletions}</span></li>
                  ))}
                </ul>
              ) : <p className="meta-empty">No files changed.</p>}
            </section>
          </div>
        </div>
      </div>
    </section>
  );
}

export function ApplicationSubmitResults({ result }: { result: ApplicationSubmitResponse }) {
  return (
    <section aria-labelledby="app-submit-heading" className="result-panel submit-results">
      <div className="result-heading">
        <span className="result-tag submit-tag">SUBMIT</span>
        <h2 id="app-submit-heading">Hidden checks complete</h2>
        <span>Coding agent · v{result.version}</span>
      </div>
      <div className="score-hero">
        <div><span>Final score</span><strong>{result.score}</strong><small>/ 100</small></div>
        <div className="score-stars" aria-label={`${result.stars} of 3 stars`}>{"★".repeat(result.stars)}<i>{"★".repeat(3 - result.stars)}</i></div>
      </div>
      <dl className="score-grid">
        <div><dt>Hidden checks</dt><dd>{result.passed} / {result.total}</dd><small>passed</small></div>
        <div><dt>Evaluation</dt><dd>{result.evaluation_score}%</dd><small>functional result</small></div>
        <div><dt>Efficiency</dt><dd>{result.efficiency}%</dd><small>{result.prompt_tokens} tokens</small></div>
        <div><dt>Stars</dt><dd>{result.stars}/3</dd><small>this submit</small></div>
        <div><dt>XP earned</dt><dd>+{result.xp_earned}</dd><small>{result.total_xp} Total XP</small></div>
        <div><dt>Best score</dt><dd>{result.best_score}</dd><small>{result.best_stars}/3 best stars</small></div>
      </dl>
      {result.screenshot !== null ? (
        <Shot
          title="SUBMITTED RESULT"
          viewport={`${result.screenshot.width}px · ${result.screenshot.label ?? result.screenshot.viewport}`}
          src={result.screenshot.image}
          alt="The page the coding agent built for this submission."
          tone="result"
        />
      ) : null}
      <p className="completion-note">
        <span>NEXT</span>
        {result.agent_status === "rejected"
          ? "The agent’s edits were rejected, so nothing was evaluated. Ask it for complete file edits to the allowed files."
          : result.stars === 3
            ? "Mastered. A shorter prompt that still passes every check raises your efficiency score."
            : result.completed
            ? "Challenge complete. Tighten the prompt to raise your score, or aim for three stars."
            : "Hidden checks test the same requirements more strictly. Use Run to inspect the result, then refine."}
      </p>
    </section>
  );
}
