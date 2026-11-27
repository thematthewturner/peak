"use client";
import { useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { useSession } from "@/lib/me";
import type { Series } from "@/lib/types";

const TITLES: Record<string, string> = {
  bluebook_clean: "Clean Bluebook (the trend that counts)",
  psat: "PSAT",
  official_sat: "Official SAT",
  bluebook_exposed: "Bluebook, not clean (shown separately)",
};

export default function Progress() {
  const { api, me } = useSession();
  const [series, setSeries] = useState<Series | null>(null);
  useEffect(() => { api<Series>("/benchmarks").then(setSeries).catch(() => {}); }, [api]);
  return (
    <Shell me={me} api={api}>
      <h1>Progress</h1>
      <p className="muted">Only unseen, single-sitting, unaided Bluebook forms count as the trend. Everything else is kept apart so it can&apos;t mislead.</p>
      {series && Object.keys(TITLES).map((k) => (
        <section key={k} className="card">
          <h2>{TITLES[k]}</h2>
          {series[k]?.length ? (
            <table>
              <thead><tr><th align="left">Date</th><th>R&amp;W</th><th>Math</th><th>Total</th></tr></thead>
              <tbody>{series[k].map((r) => (
                <tr key={r.id}><td>{r.taken_on}</td><td align="center">{r.rw ?? "–"}</td><td align="center">{r.math ?? "–"}</td><td align="center"><strong>{r.total ?? "–"}</strong></td></tr>
              ))}</tbody>
            </table>
          ) : <p className="muted">None yet.</p>}
        </section>
      ))}
    </Shell>
  );
}
