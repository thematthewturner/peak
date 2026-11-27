"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { useSession } from "@/lib/me";
import type { TodayPlan } from "@/lib/types";

const SIZES = [5, 15, 25, 40];

export default function Today() {
  const { api, me } = useSession();
  const [minutes, setMinutes] = useState(25);
  const [plan, setPlan] = useState<TodayPlan | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<TodayPlan>(`/today?minutes=${minutes}`).then(setPlan).catch((e) => setError(e.message));
  }, [api, minutes]);

  const focus = plan?.focus_candidates[0]?.skill_id;
  return (
    <Shell me={me} api={api}>
      <h1>Today</h1>
      <div className="row" role="group" aria-label="Session length">
        {SIZES.map((m) => (
          <button key={m} className="chip" aria-pressed={minutes === m} onClick={() => setMinutes(m)}>
            {m} min
          </button>
        ))}
      </div>
      {error && <p className="err" role="alert">{error}</p>}
      {plan?.throttled && (
        <p className="banner">School test coming up: Peak is keeping it to a 5-minute maintenance session.</p>
      )}
      {plan?.blocks.map((b) => (
        <section key={b.kind} className="card">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h2 style={{ textTransform: "capitalize" }}>{b.kind}</h2>
            <span className="muted">{Math.round(b.minutes)} min · {b.count} item{b.count === 1 ? "" : "s"}</span>
          </div>
          <p className="muted">{b.reason}</p>
        </section>
      ))}
      {plan && plan.blocks.length === 0 && <p className="card">Nothing due. Take a breather or pick a longer session.</p>}
      {plan && plan.deferred_verifications > 0 && (
        <p className="muted">{plan.deferred_verifications} repair check(s) are waiting; they&apos;ll be re-ranked, not lost.</p>
      )}
      <div className="row">
        <Link className="btn" href={focus ? `/practice?skill=${encodeURIComponent(focus)}` : "/practice"}>Start</Link>
        {plan && <span className="muted">{plan.days_to_target} days to the June 5 SAT</span>}
      </div>
    </Shell>
  );
}
