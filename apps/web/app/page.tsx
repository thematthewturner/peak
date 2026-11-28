"use client";
import { useEffect, useState } from "react";
import { createApi } from "@/lib/api";

const api = createApi(() => "", { redirectOn401: false });

// Peak opens straight into Today from the launcher. This page is for the parent account, or if the session ends.
export default function SignIn() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    api("/me").then(() => location.replace("/today/")).catch(() => setChecking(false));
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/login", "POST", { username, password });
      location.replace("/today/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not sign in");
      setBusy(false);
    }
  }

  if (checking) return <div className="signin" />;
  return (
    <div className="signin">
      <form onSubmit={submit}>
        <h1 className="title">Peak</h1>
        <p className="sub">Open Peak from its app icon to go straight in. This sign-in is for the parent account.</p>
        <label className="field">Username
          <input id="username" type="text" autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} />
        </label>
        <label className="field">Password
          <input id="password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {error && <p className="err" role="alert">{error}</p>}
        <button className="go" disabled={busy || !username || !password}>Sign in</button>
      </form>
    </div>
  );
}
