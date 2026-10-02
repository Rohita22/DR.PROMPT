import type { Metadata } from "next";

import { ChallengeHarness } from "@/features/challenge/challenge-harness";
import { getBackendHealth } from "@/lib/api/health";

export const metadata: Metadata = { title: "Play · DR. PROMPT" };

export default async function PlayPage() {
  const health = await getBackendHealth();
  return <ChallengeHarness backendConnected={health.status === "ok"} />;
}
