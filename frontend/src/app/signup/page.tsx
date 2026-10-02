import type { Metadata } from "next";
import { Suspense } from "react";

import { SiteHeader } from "@/components/site-header";
import { AuthForm } from "@/features/auth/auth-form";

export const metadata: Metadata = { title: "Create account · DR. PROMPT" };

export default function SignupPage() {
  return <div className="auth-page"><SiteHeader /><div className="auth-layout"><section className="auth-story signup-story"><div className="auth-story-content"><span className="badge badge-primary">START AT LEVEL 01</span><h2>Learn prompt engineering by doing it.</h2><p>No lectures. Write a prompt, see real model output, diagnose failures, and improve your score.</p><ol className="auth-steps"><li><span>01</span><div><strong>Run visible tests</strong><p>Debug with complete input and output details.</p></div></li><li><span>02</span><div><strong>Submit hidden cases</strong><p>Measure whether your prompt really generalizes.</p></div></li><li><span>03</span><div><strong>Earn stars and XP</strong><p>Unlock the next level and climb the board.</p></div></li></ol></div></section><section className="auth-panel"><Suspense fallback={<div className="account-state"><span className="spinner" /></div>}><AuthForm mode="signup" /></Suspense></section></div></div>;
}
