"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import {
  createVersion,
  publishChallenge,
  saveChallenge,
  testChallenge,
  unpublishChallenge,
} from "./api";
import { ApplicationEditor } from "./application-editor";
import { applicationValidation } from "./application-types";
import type { ApplicationPackage } from "./application-types";
import { ApplicationRunResults } from "../challenge/application-results";
import { GraderEditor } from "./grader-editor";
import { JsonEditor } from "./json-editor";
import { TestCaseEditor } from "./test-case-editor";
import type { AdminTestResult, ChallengeDefinition } from "./types";

const textSections = ["Basics", "Instructions", "Examples", "Visible Tests", "Hidden Tests", "Evaluation", "Scoring", "Model", "Preview / Test", "Publishing"];

export function ChallengeEditor({ initial, isNew = false, packages = [] }: { initial: ChallengeDefinition; isNew?: boolean; packages?: ApplicationPackage[] }) {
  const router = useRouter();
  const [challenge, setChallenge] = useState(initial);
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [candidatePrompt, setCandidatePrompt] = useState("");
  const [testResult, setTestResult] = useState<AdminTestResult | null>(null);
  const isApplication = challenge.challenge_type === "application";
  const validation = isApplication ? applicationValidation(challenge.application, packages) : null;
  const sections = isApplication ? ["Basics", "Instructions", "Application", "Visible Checks", "Hidden Checks", "Screenshots", "Execution Limits", "Scoring", "Model", "Preview / Test", "Publishing"] : textSections;
  const editable = isNew || challenge.publication_state === "draft";
  const weightsValid = useMemo(() => Math.abs(challenge.scoring.accuracy_weight + challenge.scoring.efficiency_weight - 1) < 0.000001, [challenge.scoring]);

  function patch<K extends keyof ChallengeDefinition>(key: K, value: ChallengeDefinition[K]) {
    setChallenge((current) => ({ ...current, [key]: value }));
  }

  async function action(label: string, operation: () => Promise<{ message?: string }>, after?: () => void) {
    setBusy(label); setError(""); setNotice("");
    try {
      const result = await operation();
      setNotice(result.message ?? `${label} completed.`);
      after?.();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : `${label} failed.`);
    } finally { setBusy(""); }
  }

  async function runTest() {
    if (isNew) { setError("Save this draft before testing it."); return; }
    setBusy("Testing"); setError(""); setTestResult(null);
    try { setTestResult(await testChallenge(challenge.slug, candidatePrompt)); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Challenge test failed."); }
    finally { setBusy(""); }
  }

  return (
    <main className="admin-editor-layout">
      <aside className="admin-editor-nav">
        <p className="section-kicker">AUTHORING MAP</p>
        <nav>{sections.map((item, index) => <a key={item} href={`#${item.toLowerCase().replaceAll(" ", "-").replace("/", "")}`}><span>{String(index + 1).padStart(2, "0")}</span>{item}</a>)}</nav>
        <div className="admin-version-card"><span>Editing version</span><strong>v{challenge.version}</strong><em className={`state-${challenge.publication_state}`}>{challenge.publication_state}</em></div>
      </aside>
      <div className="admin-editor-main">
        <header className="admin-editor-hero">
          <div><p className="section-kicker">CHALLENGE WORKSHOP / {challenge.track.toUpperCase()}</p><h1>{challenge.title || "Untitled challenge"}</h1><p>{editable ? "Draft changes stay private until you publish." : "This historical version is read-only. Create a new version to make changes."}</p></div>
          <div className="admin-hero-actions">
            {!editable && !isNew ? <button className="admin-secondary" disabled={Boolean(busy)} onClick={() => action("Creating version", () => createVersion(challenge.slug), () => router.refresh())}>Create new version</button> : null}
            {editable ? <button className="admin-primary" disabled={Boolean(busy) || !weightsValid || Boolean(validation)} onClick={() => action("Saving", () => saveChallenge(challenge, isNew), () => isNew ? router.push(`/admin/challenges/${challenge.slug}`) : router.refresh())}>{busy === "Saving" ? "Saving…" : "Save draft"}</button> : null}
          </div>
        </header>
        {notice ? <div className="admin-alert success">{notice}</div> : null}
        {error ? <div className="admin-alert danger" role="alert">{error}</div> : null}
        {validation ? <div className="admin-alert danger" role="alert">{validation}</div> : null}

        <fieldset disabled={!editable} className="admin-fieldset">
          <section className="admin-panel" id="basics">
            <div className="admin-section-heading"><div><p className="section-kicker">IDENTITY</p><h2>Basics</h2></div><span className="admin-index">01</span></div>
            <label className="admin-field compact"><span>Challenge type</span><select value={challenge.challenge_type} disabled={!isNew} onChange={(event) => {
              const type = event.target.value as "text" | "application";
              setChallenge((current) => ({ ...current, challenge_type: type, application: null,
                visible_examples: [], visible_test_cases: [], hidden_test_cases: [],
                model: { ...current.model, max_output_tokens: type === "application" ? 8192 : 16,
                  reasoning_effort: type === "application" ? "low" : null,
                  system_wrapper: type === "application" ? "You are a careful front-end coding agent. Follow the player's instructions and edit only the supplied HTML/CSS files. Return the requested structured file replacements." : null } }));
            }}><option value="text">TEXT · Model output</option><option value="application">APPLICATION · Coding agent</option></select><small>Type is fixed after creation.</small></label>
            <div className="admin-grid two">
              <label className="admin-field wide"><span>Title</span><input value={challenge.title} onChange={(event) => patch("title", event.target.value)} placeholder="Exact Output" /></label>
              <label className="admin-field"><span>Slug</span><input value={challenge.slug} disabled={!isNew} onChange={(event) => patch("slug", event.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))} /></label>
              <label className="admin-field"><span>Track</span><select value={challenge.track} onChange={(event) => patch("track", event.target.value as ChallengeDefinition["track"])}>{["control", "extract", "classify", "structure"].map((item) => <option key={item}>{item}</option>)}</select></label>
              <label className="admin-field"><span>Difficulty</span><select value={challenge.difficulty} onChange={(event) => patch("difficulty", event.target.value as ChallengeDefinition["difficulty"])}>{["easy", "medium", "hard", "boss"].map((item) => <option key={item}>{item}</option>)}</select></label>
              <label className="admin-field"><span>Track order</span><input type="number" min="0" value={challenge.order} onChange={(event) => patch("order", Number(event.target.value))} /></label>
              <label className="admin-field wide"><span>Description</span><textarea value={challenge.description} onChange={(event) => patch("description", event.target.value)} /></label>
            </div>
          </section>

          <section className="admin-panel" id="instructions">
            <div className="admin-section-heading"><div><p className="section-kicker">PLAYER BRIEF</p><h2>Instructions</h2></div><span className="admin-index">02</span></div>
            <label className="admin-field"><span>Objective</span><textarea value={challenge.objective} onChange={(event) => patch("objective", event.target.value)} /></label>
            <div className="admin-subsection"><div className="admin-row-heading"><strong>Constraints</strong><button className="admin-secondary" type="button" onClick={() => patch("constraints", [...challenge.constraints, ""])}>+ Add constraint</button></div>
              {challenge.constraints.map((constraint, index) => <div className="list-input" key={index}><span>{String(index + 1).padStart(2, "0")}</span><input value={constraint} onChange={(event) => patch("constraints", challenge.constraints.map((item, itemIndex) => itemIndex === index ? event.target.value : item))} /><button type="button" onClick={() => patch("constraints", challenge.constraints.filter((_, itemIndex) => itemIndex !== index))}>×</button></div>)}
            </div>
            <label className="admin-field compact"><span>Prompt hard limit</span><input type="number" min="1" value={challenge.prompt_token_limit ?? ""} onChange={(event) => patch("prompt_token_limit", event.target.value ? Number(event.target.value) : null)} /></label>
          </section>

          {isApplication ? <ApplicationEditor value={challenge.application} packages={packages} onChange={(value) => patch("application", value)} /> : <>
          <section className="admin-panel" id="examples">
            <div className="admin-section-heading"><div><p className="section-kicker">EXPLANATION</p><h2>Visible examples</h2></div><button className="admin-secondary" type="button" onClick={() => patch("visible_examples", [...challenge.visible_examples, { input: "", expected_output: "", explanation: null }])}>+ Add example</button></div>
            {challenge.visible_examples.length === 0 ? <div className="admin-empty">Examples explain the mechanic but are not executable tests.</div> : null}
            <div className="authoring-list">{challenge.visible_examples.map((example, index) => <article className="authoring-item" key={index}><header><strong>EX {String(index + 1).padStart(2, "0")}</strong><button type="button" className="admin-text danger" onClick={() => patch("visible_examples", challenge.visible_examples.filter((_, itemIndex) => itemIndex !== index))}>Remove</button></header><div className="admin-grid two"><JsonEditor label="Input" value={example.input} onChange={(input) => patch("visible_examples", challenge.visible_examples.map((item, itemIndex) => itemIndex === index ? { ...item, input } : item))} /><JsonEditor label="Expected output" value={example.expected_output} onChange={(expected_output) => patch("visible_examples", challenge.visible_examples.map((item, itemIndex) => itemIndex === index ? { ...item, expected_output } : item))} /></div><label className="admin-field"><span>Explanation</span><input value={example.explanation ?? ""} onChange={(event) => patch("visible_examples", challenge.visible_examples.map((item, itemIndex) => itemIndex === index ? { ...item, explanation: event.target.value || null } : item))} /></label></article>)}</div>
          </section>

          <TestCaseEditor title="Visible tests" tests={challenge.visible_test_cases} onChange={(value) => patch("visible_test_cases", value)} />
          <TestCaseEditor title="Hidden tests" privateTests tests={challenge.hidden_test_cases} onChange={(value) => patch("hidden_test_cases", value)} />

          <section className="admin-panel" id="evaluation">
            <div className="admin-section-heading"><div><p className="section-kicker">FALLBACK</p><h2>Evaluation</h2></div><span className="admin-index">06</span></div>
            <p className="admin-help">Each test stores its effective grader. This default is retained for challenge-level evaluation configuration.</p>
            <GraderEditor value={challenge.default_grader} onChange={(value) => patch("default_grader", value)} />
          </section>

          </>}
          <section className="admin-panel" id="scoring">
            <div className="admin-section-heading"><div><p className="section-kicker">MASTERY MODEL</p><h2>Scoring</h2></div><span className="admin-index">07</span></div>
            <div className="admin-grid two"><label className="admin-field"><span>Accuracy weight</span><input type="number" step="0.05" min="0" max="1" value={challenge.scoring.accuracy_weight} onChange={(event) => patch("scoring", { ...challenge.scoring, accuracy_weight: Number(event.target.value) })} /></label><label className="admin-field"><span>Efficiency weight</span><input type="number" step="0.05" min="0" max="1" value={challenge.scoring.efficiency_weight} onChange={(event) => patch("scoring", { ...challenge.scoring, efficiency_weight: Number(event.target.value) })} /></label></div>
            {!weightsValid ? <p className="field-error">Accuracy and efficiency weights must total 1.0.</p> : null}
            <div className="admin-subsection"><div className="admin-row-heading"><strong>Efficiency tiers</strong><button className="admin-secondary" type="button" onClick={() => patch("scoring", { ...challenge.scoring, efficiency_tiers: [...challenge.scoring.efficiency_tiers, { max_tokens: 300, score: 40 }] })}>+ Add tier</button></div>{challenge.scoring.efficiency_tiers.map((tier, index) => <div className="tier-row" key={index}><span>≤</span><input aria-label="Maximum tokens" type="number" value={tier.max_tokens} onChange={(event) => patch("scoring", { ...challenge.scoring, efficiency_tiers: challenge.scoring.efficiency_tiers.map((item, itemIndex) => itemIndex === index ? { ...item, max_tokens: Number(event.target.value) } : item) })} /><span>tokens →</span><input aria-label="Efficiency score" type="number" value={tier.score} onChange={(event) => patch("scoring", { ...challenge.scoring, efficiency_tiers: challenge.scoring.efficiency_tiers.map((item, itemIndex) => itemIndex === index ? { ...item, score: Number(event.target.value) } : item) })} /><button type="button" onClick={() => patch("scoring", { ...challenge.scoring, efficiency_tiers: challenge.scoring.efficiency_tiers.filter((_, itemIndex) => itemIndex !== index) })}>×</button></div>)}</div>
            <div className="admin-grid four"><label className="admin-field"><span>Above max score</span><input type="number" value={challenge.scoring.score_above_max} onChange={(event) => patch("scoring", { ...challenge.scoring, score_above_max: Number(event.target.value) })} /></label><label className="admin-field"><span>1 star accuracy</span><input type="number" value={challenge.scoring.one_star} onChange={(event) => patch("scoring", { ...challenge.scoring, one_star: Number(event.target.value) })} /></label><label className="admin-field"><span>2 star accuracy</span><input type="number" value={challenge.scoring.two_stars} onChange={(event) => patch("scoring", { ...challenge.scoring, two_stars: Number(event.target.value) })} /></label><label className="admin-field"><span>3 star max tokens</span><input type="number" value={challenge.scoring.three_star_max_prompt_tokens ?? ""} onChange={(event) => patch("scoring", { ...challenge.scoring, three_star_max_prompt_tokens: event.target.value ? Number(event.target.value) : null })} /></label></div>
          </section>

          <section className="admin-panel" id="model">
            <div className="admin-section-heading"><div><p className="section-kicker">EXECUTION</p><h2>Model</h2></div><span className="admin-index">08</span></div>
            <div className="admin-grid three"><label className="admin-field"><span>Model identifier</span><input value={challenge.model.model_id} onChange={(event) => patch("model", { ...challenge.model, model_id: event.target.value })} /></label><label className="admin-field"><span>Temperature</span><input type="number" min="0" max="2" step="0.1" value={challenge.model.temperature} onChange={(event) => patch("model", { ...challenge.model, temperature: Number(event.target.value) })} /></label><label className="admin-field"><span>Max output tokens</span><input type="number" min="1" value={challenge.model.max_output_tokens} onChange={(event) => patch("model", { ...challenge.model, max_output_tokens: Number(event.target.value) })} /></label></div>
            <label className="admin-field"><span>System wrapper</span><textarea value={challenge.model.system_wrapper ?? ""} onChange={(event) => patch("model", { ...challenge.model, system_wrapper: event.target.value || null })} /></label>
          </section>
        </fieldset>

        <section className="admin-panel admin-test-panel" id="preview--test">
          <div className="admin-section-heading"><div><p className="section-kicker">NO SIDE EFFECTS</p><h2>Preview / Test</h2></div><span className="admin-index">09</span></div>
          <p className="admin-help">Executes visible and hidden tests without creating a submission, XP, progress, or leaderboard entry.</p>
          <p className="admin-help">Testing uses the saved version. Save draft changes before testing.</p>
          <textarea aria-label="Candidate player prompt" className="candidate-prompt" value={candidatePrompt} onChange={(event) => setCandidatePrompt(event.target.value)} placeholder="Enter a candidate player prompt…" />
          <button className="admin-primary" disabled={Boolean(busy) || !candidatePrompt.trim()} onClick={runTest}>{busy === "Testing" ? "Testing…" : "Test challenge"}</button>
          {testResult ? <AdminTestResults result={testResult} /> : null}
        </section>

        <section className="admin-panel publishing-panel" id="publishing">
          <div className="admin-section-heading"><div><p className="section-kicker">VERSION CONTROL</p><h2>Publishing</h2></div><span className="admin-index">10</span></div>
          <div className="publication-summary"><div><span>Authoring version</span><strong>v{challenge.version}</strong></div><div><span>Active version</span><strong>{challenge.current_version ? `v${challenge.current_version}` : "None"}</strong></div><div><span>Status</span><strong className={`state-${challenge.publication_state}`}>{challenge.publication_state}</strong></div></div>
          <div className="publishing-actions">{challenge.publication_state === "draft" && !isNew ? <button className="admin-primary" disabled={Boolean(busy)} onClick={() => action("Publishing", () => publishChallenge(challenge.slug, challenge.version), () => router.refresh())}>Publish version</button> : null}{challenge.current_version ? <button className="admin-danger" disabled={Boolean(busy)} onClick={() => action("Unpublishing", () => unpublishChallenge(challenge.slug), () => router.refresh())}>Unpublish challenge</button> : null}</div>
          {challenge.versions?.length ? <div className="version-history">{challenge.versions.map((version) => <div key={version.version}><strong>v{version.version}</strong><span className={`state-${version.publication_state}`}>{version.publication_state}</span><time>{new Date(version.created_at).toLocaleDateString()}</time></div>)}</div> : null}
        </section>
      </div>
    </main>
  );
}

export function AdminTestResults({ result }: { result: AdminTestResult }) {
  return <div className="admin-test-results">
    <div className="admin-score-strip"><strong>{result.score}</strong><span>score</span><b>{result.passed}/{result.total} passed</b><b>{result.accuracy}% {result.application ? "evaluation" : "accuracy"}</b><b>{result.prompt_tokens} tokens</b><b>{"★".repeat(result.stars)}{"☆".repeat(3 - result.stars)}</b></div>
    {result.application ? <>
      <ApplicationRunResults result={result.application} />
      <div className="result-group private"><h3>Hidden checks · private</h3>{result.hidden_checks?.map((check) => <article key={check.id} className={`admin-test ${check.passed ? "passed" : "failed"}`}><header><strong>{check.label}</strong><span>{check.passed ? "PASS" : "FAIL"}</span></header>{check.message ? <p>{check.message}</p> : null}</article>)}</div>
    </> : <><ResultGroup title="Visible tests" tests={result.visible_tests} /><ResultGroup title="Hidden tests · private" tests={result.hidden_tests} privateTests /></>}
  </div>;
}


function ResultGroup({ title, tests, privateTests = false }: { title: string; tests: AdminTestResult["visible_tests"]; privateTests?: boolean }) {
  return <div className={privateTests ? "result-group private" : "result-group"}><h3>{title}</h3>{tests.map((test) => <article key={test.id} className={test.passed ? "admin-test passed" : "admin-test failed"}><header><strong>{test.id}</strong><span>{test.passed ? "PASS" : "FAIL"}</span></header><dl><div><dt>Input</dt><dd>{JSON.stringify(test.input)}</dd></div><div><dt>Expected</dt><dd>{JSON.stringify(test.expected)}</dd></div><div><dt>Actual</dt><dd>{JSON.stringify(test.actual)}</dd></div></dl>{test.failure_reason ? <small>{test.failure_reason}</small> : null}</article>)}</div>;
}

