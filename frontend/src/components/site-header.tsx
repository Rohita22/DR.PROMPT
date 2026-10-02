import Link from "next/link";

export function SiteHeader({
  tone = "light",
  active,
}: {
  tone?: "light" | "dark";
  active?: "profile";
}) {
  return (
    <header className={`site-header site-header-${tone}`}>
      <Link className="site-brand" href="/" aria-label="Dr. Prompt home">
        <span className="brand-glyph">D</span>
        <span>DR. PROMPT</span>
      </Link>
      <nav className="site-nav" aria-label="Primary navigation">
        <Link href="/#how-it-works">How it works</Link>
        <Link href="/#curriculum">Curriculum</Link>
        <Link href="/profile" aria-current={active === "profile" ? "page" : undefined}>Profile</Link>
      </nav>
      <div className="site-actions">
        <Link className="site-login" href="/login">Sign in</Link>
        <Link className="site-cta" href="/play">Start playing <span>→</span></Link>
      </div>
    </header>
  );
}
