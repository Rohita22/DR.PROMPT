import { getBackendHealth } from "@/lib/api/health";
import { ChallengeHarness } from "@/features/challenge/challenge-harness";

export default async function Home() {
  const health = await getBackendHealth();

  return <ChallengeHarness backendConnected={health.status === "ok"} />;
}
