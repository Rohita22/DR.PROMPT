import type { ApplicationPackage } from "@/features/admin/application-types";
import { AdminGate } from "@/features/admin/admin-gate";
import { AdminShell } from "@/features/admin/admin-shell";
import { ChallengeEditor } from "@/features/admin/challenge-editor";
import { emptyChallenge } from "@/features/admin/types";
import { adminServerFetch, hasAdminSession } from "@/lib/admin/server-auth";

export default async function NewChallengePage() {
  if (!(await hasAdminSession())) return <AdminGate />;
  const catalog = await adminServerFetch("application-packages");
  const packages: ApplicationPackage[] = catalog.ok ? await catalog.json() : [];
  return <AdminShell title="New challenge"><ChallengeEditor packages={packages} initial={emptyChallenge()} isNew /></AdminShell>;
}

