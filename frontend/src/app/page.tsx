import Link from "next/link";

import { SiteHeader } from "@/components/site-header";

const loop = [
  { number: "01", title: "Write", body: "Turn the objective and constraints into clear model instructions." },
  { number: "02", title: "Run", body: "Debug against visible cases with expected and actual output." },
  { number: "03", title: "Submit", body: "Test generalization against hidden cases that stay server-side." },
  { number: "04", title: "Improve", body: "Use your score and safe feedback to make the next version better." },
];

export default function Home() {
  return (
    <div className="landing-page">
      <SiteHeader />
      <main>
        <section className="landing-hero">
          <div className="hero-copy">
            <div className="hero-eyebrow"><span /> THE PROMPT ENGINEERING GAME</div>
            <h1>Learn prompting.<br /><em>Prove it works.</em></h1>
            <p>Master prompt engineering through scored, hands-on challenges. Write instructions, test real outputs, and improve until your prompt survives every hidden case.</p>
            <div className="hero-actions"><Link className="hero-primary" href="/play">Play the first challenge <span>→</span></Link><a className="hero-secondary" href="#how-it-works">See how it works <span>↓</span></a></div>
            <div className="hero-note"><span className="hero-avatars"><i>A</i><i>M</i><i>J</i></span><span>Built for developers, technical learners,<br />and prompt practitioners.</span></div>
          </div>
          <div className="hero-demo" aria-label="Example prompt challenge">
            <div className="demo-top"><span>DR. PROMPT</span><div>CONTROL <i>/</i> LEVEL 01</div><span className="demo-online"><i /> LIVE MODEL</span></div>
            <div className="demo-body">
              <div className="demo-brief"><div className="badge-row"><span className="badge badge-primary">LEVEL 01</span><span className="badge">CONTROL</span><span className="badge badge-success">EASY</span></div><h2>Exact Output</h2><p>Return exactly YES when the service is available, otherwise return exactly NO.</p><span className="demo-label">CONSTRAINTS</span><ol><li><span>01</span>Only YES or NO</li><li><span>02</span>Uppercase, no punctuation</li><li><span>03</span>Judge current availability</li></ol></div>
              <div className="demo-editor"><div className="demo-editor-head"><span>PROMPT</span><span><i /> 18 / 120 tokens</span></div><code>Return exactly YES when the service is currently available, otherwise return exactly NO.</code><div className="demo-actions"><button>Run <kbd>⌘↵</kbd></button><button>Submit <span>→</span></button></div><div className="demo-result"><header><span className="status-tag">PASS</span><strong>3 / 3 visible passing</strong><small>Debug only</small></header><div><span>INPUT</span><code>The API is responding normally.</code></div><div><span>EXPECTED</span><code>YES</code></div><div><span>ACTUAL</span><code className="demo-success">YES</code></div></div></div>
            </div>
          </div>
        </section>

        <section className="landing-loop" id="how-it-works">
          <div className="landing-section-heading"><span className="section-kicker">THE CORE LOOP</span><h2>Practice the skill,<br />not the theory.</h2><p>Every challenge creates a tight feedback loop between your instructions and observable model behavior.</p></div>
          <div className="loop-grid">{loop.map((item) => <article key={item.number}><span>{item.number}</span><h3>{item.title}</h3><p>{item.body}</p><i>→</i></article>)}</div>
        </section>

        <section className="curriculum-section" id="curriculum">
          <div className="curriculum-copy"><span className="section-kicker">CURRICULUM</span><h2>From precise outputs to compound instructions.</h2><p>Start with CONTROL fundamentals, then build toward extraction, classification, structured data, and combined boss challenges.</p><Link href="/play">Explore the CONTROL track →</Link></div>
          <div className="track-list"><article className="track-active"><span>01</span><div><strong>CONTROL</strong><p>Direct the model and constrain its response.</p></div><em>5 LEVELS · AVAILABLE</em></article><article><span>02</span><div><strong>EXTRACT</strong><p>Pull exact facts from noisy source material.</p></div><em>COMING NEXT</em></article><article><span>03</span><div><strong>CLASSIFY</strong><p>Build reliable boundaries between categories.</p></div><em>PLANNED</em></article><article><span>04</span><div><strong>STRUCTURE</strong><p>Produce valid, useful machine-readable output.</p></div><em>PLANNED</em></article></div>
        </section>

        <section className="score-section"><div className="score-copy"><span className="section-kicker">OBJECTIVE SCORING</span><h2>Good prompts do more with less.</h2><p>Your final score balances correctness on hidden tests with prompt efficiency. Clear instructions win; unnecessary tokens do not.</p><div className="score-formula"><div><strong>80%</strong><span>Accuracy</span></div><i>+</i><div><strong>20%</strong><span>Efficiency</span></div><i>=</i><div><strong>100</strong><span>Perfect score</span></div></div></div><div className="score-card"><span>FINAL SCORE</span><div><strong>96.7</strong><small>/ 100</small></div><div className="score-card-stars">★★★</div><dl><div><dt>Hidden tests</dt><dd>6 / 6</dd></div><div><dt>Prompt tokens</dt><dd>34</dd></div><div><dt>XP earned</dt><dd>+175</dd></div></dl></div></section>

        <section className="landing-cta"><span className="section-kicker">YOUR FIRST CHALLENGE IS READY</span><h2>Can you make the model<br />say exactly what you mean?</h2><p>No setup. No course prerequisite. Start with visible tests and iterate from there.</p><Link href="/play">Start Level 01 <span>→</span></Link></section>
      </main>
      <footer className="landing-footer"><Link className="site-brand" href="/"><span className="brand-glyph">D</span><span>DR. PROMPT</span></Link><p>Learn prompt engineering by building prompts that work.</p><div><Link href="/play">Play</Link><Link href="/login">Sign in</Link><Link href="/account">Progress</Link></div><span>© 2026 DR. PROMPT</span></footer>
    </div>
  );
}
