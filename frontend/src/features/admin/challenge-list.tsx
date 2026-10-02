import Link from "next/link";

import type { AdminChallengeSummary } from "./types";

export function AdminChallengeList({ challenges }: { challenges: AdminChallengeSummary[] }) {
  if (challenges.length === 0) {
    return <div className="admin-empty-state"><span>01</span><h2>No authored challenges yet</h2><p>Create the first draft and keep it private until its tests are ready.</p><Link className="admin-primary" href="/admin/challenges/new">Create challenge</Link></div>;
  }
  return (
    <div className="admin-challenge-table">
      <div className="admin-table-head"><span>Order</span><span>Challenge</span><span>Track</span><span>Version</span><span>Tests</span><span>Status</span><span /></div>
      {challenges.map((item) => <article key={item.slug}><span className="order-cell">{String(item.order).padStart(2, "0")}</span><div><strong>{item.title}</strong><code>{item.slug}</code></div><span className="admin-chip">{item.track}</span><span>v{item.version}<small>{item.difficulty}</small></span><span>{item.visible_test_count} visible<small>{item.hidden_test_count} hidden</small></span><span className={`state-${item.publication_state}`}>{item.publication_state}</span><Link href={`/admin/challenges/${item.slug}`}>Edit →</Link></article>)}
    </div>
  );
}

