import type { ApplicationPackage } from "@/features/admin/application-types";
import { notFound } from "next/navigation";

import { AdminGate } from "@/features/admin/admin-gate";
import { AdminShell } from "@/features/admin/admin-shell";
import { ChallengeEditor } from "@/features/admin/challenge-editor";
import type { ChallengeDefinition } from "@/features/admin/types";
import { adminServerFetch, hasAdminSession } from "@/lib/admin/server-auth";

export default async function EditChallengePage({ params }: { params: Promise<{ slug: string }> }) {
  if (!(await hasAdminSession())) return <AdminGate />;
  const { slug } = await params;
  const response = await adminServerFetch(`challenges/${encodeURIComponent(slug)}`);
  if (response.status === 404) notFound();
  if (!response.ok) return <AdminShell title="Unavailable"><main className="admin-list-page"><div className="admin-alert danger">This challenge could not be loaded.</div></main></AdminShell>;
  const challenge = await response.json() as ChallengeDefinition;
  const catalog = await adminServerFetch("application-packages");
  const packages: ApplicationPackage[] = catalog.ok ? await catalog.json() : [];
  return <AdminShell title={challenge.title}><ChallengeEditor key={`${challenge.version}:${challenge.updated_at}`} packages={packages} initial={challenge} /></AdminShell>;
}
