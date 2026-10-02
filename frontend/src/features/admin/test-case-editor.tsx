"use client";

import { GraderEditor } from "./grader-editor";
import { JsonEditor } from "./json-editor";
import type { AuthoringTest } from "./types";

export function TestCaseEditor({
  title,
  privateTests = false,
  tests,
  onChange,
}: {
  title: string;
  privateTests?: boolean;
  tests: AuthoringTest[];
  onChange: (tests: AuthoringTest[]) => void;
}) {
  function update(index: number, next: AuthoringTest) {
    onChange(tests.map((item, itemIndex) => itemIndex === index ? next : item));
  }
  function move(index: number, offset: number) {
    const target = index + offset;
    if (target < 0 || target >= tests.length) return;
    const next = [...tests];
    [next[index], next[target]] = [next[target], next[index]];
    onChange(next);
  }
  return (
    <section className={`admin-panel test-authoring ${privateTests ? "private-panel" : ""}`} id={privateTests ? "hidden-tests" : "visible-tests"}>
      <div className="admin-section-heading">
        <div><p className="section-kicker">{privateTests ? "SERVER-ONLY" : "DEBUGGABLE"}</p><h2>{title}</h2></div>
        <button className="admin-secondary" type="button" onClick={() => onChange([...tests, { id: `${privateTests ? "hidden" : "visible"}-${tests.length + 1}`, input: "", expected_output: "", grader: { type: "exact_match" } }])}>+ Add test</button>
      </div>
      {privateTests ? <p className="private-note">Hidden inputs and answers are restricted to this protected authoring surface.</p> : null}
      {tests.length === 0 ? <div className="admin-empty">No tests yet. Add one to define executable behavior.</div> : null}
      <div className="authoring-list">
        {tests.map((test, index) => (
          <article className="authoring-item" key={`${test.id}-${index}`}>
            <header><strong>{String(index + 1).padStart(2, "0")}</strong><input aria-label="Test ID" value={test.id} onChange={(event) => update(index, { ...test, id: event.target.value })} /><button aria-label="Move test up" type="button" className="admin-text" disabled={index === 0} onClick={() => move(index, -1)}>↑</button><button aria-label="Move test down" type="button" className="admin-text" disabled={index === tests.length - 1} onClick={() => move(index, 1)}>↓</button><button type="button" className="admin-text danger" onClick={() => onChange(tests.filter((_, itemIndex) => itemIndex !== index))}>Remove</button></header>
            <div className="admin-grid two"><JsonEditor label="Input" value={test.input} onChange={(input) => update(index, { ...test, input })} /><JsonEditor label="Expected output" value={test.expected_output} onChange={(expected_output) => update(index, { ...test, expected_output })} /></div>
            <GraderEditor value={test.grader} onChange={(grader) => update(index, { ...test, grader })} />
          </article>
        ))}
      </div>
    </section>
  );
}
