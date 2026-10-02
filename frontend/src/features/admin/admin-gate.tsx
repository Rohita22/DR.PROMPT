export function AdminGate({ invalid = false }: { invalid?: boolean }) {
  return (
    <main className="admin-gate">
      <div className="admin-gate-card">
        <p className="section-kicker">RESTRICTED TOOLING</p>
        <h1>Challenge workshop</h1>
        <p>Enter the server-configured admin key to open this browser session.</p>
        {invalid ? <p className="admin-alert danger">That admin key was not accepted.</p> : null}
        <form action="/api/admin/session" method="post">
          <label htmlFor="admin_key">Admin key</label>
          <input id="admin_key" name="admin_key" type="password" autoComplete="current-password" required />
          <button className="admin-primary" type="submit">Unlock builder</button>
        </form>
        <small>The key is handled by the Next.js server and is never saved in browser storage.</small>
      </div>
    </main>
  );
}

