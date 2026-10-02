import Link from "next/link";
import type { ReactNode } from "react";

export function AdminShell({ children, title }: { children: ReactNode; title: string }) {
  return (
    <div className="admin-shell">
      <header className="admin-topbar">
        <Link className="site-brand" href="/">
          <span className="brand-glyph">D</span><span>DR. PROMPT</span>
        </Link>
        <span className="admin-divider" />
        <Link href="/admin/challenges">Challenge Builder</Link>
        <strong>{title}</strong>
        <div className="admin-signout">
          <Link href="/play">Player view ↗</Link>
        </div>
      </header>
      {children}
    </div>
  );
}
