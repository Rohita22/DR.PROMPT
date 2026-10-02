import type { Metadata } from "next";
import { Suspense } from "react";

import { SiteHeader } from "@/components/site-header";
import { AuthForm } from "@/features/auth/auth-form";

export const metadata: Metadata = { title: "Sign in · DR. PROMPT" };

export default function LoginPage() {
  return <div className="auth-page"><SiteHeader /><div className="auth-layout"><section className="auth-story"><div className="auth-story-content"><span className="badge badge-primary">WRITE · RUN · IMPROVE</span><h2>Build prompts that survive the hidden cases.</h2><p>Practice against visible examples, submit against secret tests, and learn exactly where your instructions break.</p><div className="auth-proof"><div><strong>5</strong><span>CONTROL levels</span></div><div><strong>3</strong><span>stars per challenge</span></div><div><strong>∞</strong><span>replays</span></div></div></div><div className="auth-code-card"><div><span>PROMPT</span><i>18 / 120 tokens</i></div><code>Return exactly YES when the service is currently available, otherwise return exactly NO.</code><footer><span className="status-tag">PASS</span><span>3 / 3 visible tests</span></footer></div></section><section className="auth-panel"><Suspense fallback={<div className="account-state"><span className="spinner" /></div>}><AuthForm mode="login" /></Suspense></section></div></div>;
}
