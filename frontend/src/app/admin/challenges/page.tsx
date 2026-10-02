import Link from "next/link";

import { AdminGate } from "@/features/admin/admin-gate";
import { AdminChallengeList } from "@/features/admin/challenge-list";
import { AdminShell } from "@/features/admin/admin-shell";
import type { AdminChallengeSummary } from "@/features/admin/types";
import { adminServerFetch, hasAdminSession } from "@/lib/admin/server-auth";

export default async function AdminChallengesPage({ searchParams }: { searchParams: Promise<{ admin_error?: string }> }) {
  const params = await searchParams;
  if (!(await hasAdminSession())) return <AdminGate invalid={params.admin_error === "1"} />;
  const response = await adminServerFetch("challenges");
  const payload = response.ok ? await response.json() as { challenges: AdminChallengeSummary[] } : { challenges: [] };
  return <AdminShell title="All challenges"><main className="admin-list-page"><header className="admin-page-heading"><div><p className="section-kicker">CONTENT SYSTEM</p><h1>Challenge library</h1><p>Draft, test, version, and publish deterministic prompt challenges.</p></div><Link className="admin-primary" href="/admin/challenges/new">+ New challenge</Link></header>{!response.ok ? <div className="admin-alert danger">The challenge library could not be loaded.</div> : null}<AdminChallengeList challenges={payload.challenges} /></main></AdminShell>;
}

