"use client";
import { useEffect, useState } from "react";
import { createApi } from "@/lib/api";

const api = createApi(() => "", { redirectOn401: false });

export default function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api("/me").then(() => location.replace("/today")).catch(() => {});
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/login", "POST", { username, password });
      location.replace("/today");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not sign in");
      setBusy(false);
    }
  }

  return (
    <main className="shell">
      <form className="card" onSubmit={submit}>
        <h1>Peak</h1>
        <p className="muted">Know exactly which points you&apos;re losing. Fix them once. Prove it on a question you&apos;ve never seen.</p>
        <label>
          Username
          <input type="text" autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} />
        </label>
        <label>
          Password
          <input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {error && <p className="err" role="alert">{error}</p>}
        <button className="btn" disabled={busy || !username || !password}>Sign in</button>
      </form>
    </main>
  );
}
