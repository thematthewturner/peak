"use client";
import { useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { useSession } from "@/lib/me";
import type { Ticket } from "@/lib/types";

const LABEL: Record<string, string> = {
  OPEN: "Needs a repair", REPAIRING: "Repairing", RETRY_DUE: "Retry due", TRANSFER_DUE: "Proof due (7+ days)",
  CONFIRMED: "Fixed and proven", MAINTAIN: "Maintaining", REOPENED: "Reopened",
};

export default function Tickets() {
  const { api, me } = useSession();
  const [rows, setRows] = useState<Ticket[] | null>(null);
  const [error, setError] = useState("");
  const load = () => api<Ticket[]>("/tickets").then(setRows).catch((e) => setError(e.message));
  useEffect(() => { void load(); }, [api]); // eslint-disable-line react-hooks/exhaustive-deps

  async function step(t: Ticket, action: "start" | "complete") {
    try {
      await api(`/tickets/${t.id}/repair/${action}`, "POST", action === "start" ? { intervention: "worked_example" } : undefined);
      await load();
    } catch (e) { setError(e instanceof Error ? e.message : "Failed"); }
  }

  return (
    <Shell me={me} api={api}>
      <h1>Fixes</h1>
      {error && <p className="err" role="alert">{error}</p>}
      {rows?.length === 0 && <p className="card">No open fixes yet. Misses you confirm in Practice show up here.</p>}
      {rows?.map((t) => (
        <section key={t.id} className="card">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h2>{t.micro_skill?.replaceAll("_", " ") ?? t.cause.replace("_", " ")}</h2>
            <span className={t.state === "CONFIRMED" || t.state === "MAINTAIN" ? "ok" : t.state === "REOPENED" ? "bad" : "muted"}>{LABEL[t.state] ?? t.state}</span>
          </div>
          {t.cue && <p className="banner">Cue: {t.cue}</p>}
          {t.reopen_reason && <p className="warn">Reopened: {t.reopen_reason}</p>}
          {t.next_due && <p className="muted">Next check: {t.next_due}</p>}
          <div className="row">
            {(t.state === "OPEN" || t.state === "REOPENED") && <button className="btn" onClick={() => step(t, "start")}>Start repair</button>}
            {t.state === "REPAIRING" && <button className="btn" onClick={() => step(t, "complete")}>I&apos;ve done the repair</button>}
          </div>
        </section>
      ))}
    </Shell>
  );
}
