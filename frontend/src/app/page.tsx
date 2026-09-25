import { getBackendHealth } from "@/lib/api/health";

export default async function Home() {
  const health = await getBackendHealth();

  return (
    <main className="grid min-h-screen place-items-center px-6">
      <section className="text-center">
        <p className="mb-2 text-xs font-semibold tracking-[0.3em] text-zinc-500">
          SYSTEM STATUS
        </p>
        <h1 className="text-4xl font-bold tracking-tight">DR. PROMPT</h1>
        <p className="mt-3 text-zinc-400">Development environment ready.</p>
        <p className="mt-6 text-sm text-zinc-500" role="status">
          Backend: {health.status === "ok" ? "connected" : "unavailable"}
        </p>
      </section>
    </main>
  );
}

