"use client";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import Shell from "@/components/Shell";
import Topo from "@/components/Topo";
import { capitalize, daysToSat, DOMAIN, greeting } from "@/lib/format";
import { useSession } from "@/lib/me";
import type { SkillMap, TodayPlan } from "@/lib/types";

const SIZES = [5, 15, 25, 40];
const TITLE: Record<string, string> = { verification: "Repair checks", cards: "Rule cards", focus: "Focus", mixed: "Mixed finish" };

export default function Today() {
  const { api, me } = useSession();
  const router = useRouter();
  const [minutes, setMinutes] = useState(25);
  const [plan, setPlan] = useState<TodayPlan | null>(null);
  const [skills, setSkills] = useState<SkillMap>({});
  const [error, setError] = useState("");

  useEffect(() => {
    if (!me) return;
    api<TodayPlan>(`/today?minutes=${minutes}`).then(setPlan).catch((e) => setError(e.message));
  }, [api, me, minutes]);
  useEffect(() => { if (me) api<SkillMap>("/skills").then(setSkills).catch(() => {}); }, [api, me]);

  const focus = plan?.focus_candidates[0]?.skill_id;
  const focusName = focus && skills[focus] ? `${DOMAIN[skills[focus].domain] ?? ""}: ${skills[focus].name}` : "Your top-priority skill";
  const start = useCallback(() => {
    if (!plan) return;
    const onlyCards = plan.blocks.length > 0 && plan.blocks.every((b) => b.kind === "cards");
    router.push(onlyCards ? "/cards/" : focus ? `/practice/?skill=${encodeURIComponent(focus)}` : "/practice/");
  }, [plan, focus, router]);
  const onKey = useCallback((e: KeyboardEvent) => {
    if (e.key === "Enter") { e.preventDefault(); start(); }
  }, [start]);

  const total = plan?.blocks.reduce((s, b) => s + b.minutes, 0) || 1;
  return (
    <Shell me={me} api={api} onKey={onKey}>
      <Topo />
      <div className="view">
        <div>
          <p className="sub">{daysToSat()} days to June 5 · {new Date().toLocaleDateString("en-US", { weekday: "long" })}</p>
          <h1 className="title">{greeting()}{me ? `, ${capitalize(me.username)}` : ""}</h1>
        </div>
        <div className="seg" role="group" aria-label="Session length">
          {SIZES.map((m) => <button key={m} aria-pressed={minutes === m} onClick={() => setMinutes(m)}>{m} min</button>)}
        </div>
        {error && <p className="err" role="alert">{error}</p>}
        {plan?.throttled && <p className="banner">School test coming up, so today is a five-minute maintenance session. Nothing due is lost.</p>}
        {plan && plan.blocks.length > 0 && (
          <div className="plan">
            <div className="bar" aria-hidden="true">{plan.blocks.map((b) => <span key={b.kind} className={`k-${b.kind}`} style={{ flex: b.minutes / total }} />)}</div>
            <div>
              {plan.blocks.map((b) => (
                <div className="block" key={b.kind}>
                  <span className={`dot k-${b.kind}`} />
                  <span><b>{b.kind === "focus" ? focusName : TITLE[b.kind] ?? b.kind}</b><span className="why">{b.kind === "focus" ? "Your highest priority right now" : b.reason}</span></span>
                  <span className="min">{Math.round(b.minutes)} min</span>
                </div>
              ))}
            </div>
          </div>
        )}
        {plan && plan.blocks.length === 0 && <p className="sub">You&apos;re caught up. Five minutes of cards, or call it.</p>}
        {plan && plan.deferred_verifications > 0 && <p className="hint">{plan.deferred_verifications} repair check(s) wait for another day. They&apos;re re-ranked, never lost.</p>}
        <div className="row">
          <button className="go" onClick={start} disabled={!plan}>Start {plan?.minutes ?? minutes} minutes</button>
          <span className="hint">or press Return</span>
        </div>
      </div>
    </Shell>
  );
}
