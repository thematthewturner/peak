"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import MathText from "@/components/MathText";
import QuestionCard from "@/components/QuestionCard";
import Shell from "@/components/Shell";
import Solved from "@/components/Solved";
import { tipFaded, tipFor, WHY } from "@/lib/coach";
import { DOMAIN, shortDate } from "@/lib/format";
import { useSession } from "@/lib/me";
import type { Card, GuidedPlan, Item, SkillMap, Solved as SolvedItem, Stats, Step, Summary, Taxonomy } from "@/lib/types";

// A guided session: re-attempts from her log, rule cards, worked examples for a new math skill, then a mixed
// set. Each block says why it's there. Ends with a debrief that names what happened and when it comes back.

function WorkedStep({ api, step, sessionId, onDone, keyRef }: {
  api: ReturnType<typeof useSession>["api"]; step: Step; sessionId: string; onDone: () => void;
  keyRef: { current: ((e: KeyboardEvent) => void) | null };
}) {
  const [item, setItem] = useState<SolvedItem | null>(null);
  useEffect(() => {
    api<SolvedItem>(`/items/${step.item_id}/study`, "POST", { idempotency_key: `study-${sessionId}-${step.item_id}`, session_id: sessionId })
      .then(setItem).catch(() => onDone());
  }, [api, step.item_id, sessionId, onDone]);
  useLayoutEffect(() => { keyRef.current = (e) => { if (e.key === "Enter") { e.preventDefault(); onDone(); } }; });
  if (!item) return <p className="sub">Loading a solved example…</p>;
  return (
    <div className="worked">
      <div className="note info"><b>Worked example.</b><span>Read it once. Then cover the explanation and say the key step out loud before you move on.</span></div>
      <Solved item={item} />
      <div className="row"><button className="go" onClick={onDone}>Got it, my turn</button><span className="hint">Return</span></div>
    </div>
  );
}

function CardsStep({ api, count, onDone, keyRef }: {
  api: ReturnType<typeof useSession>["api"]; count: number; onDone: () => void;
  keyRef: { current: ((e: KeyboardEvent) => void) | null };
}) {
  const [cards, setCards] = useState<Card[] | null>(null);
  const [shown, setShown] = useState(false);
  const [t0, setT0] = useState(() => Date.now());
  useEffect(() => { api<Card[]>(`/cards/due?limit=${count}`).then((c) => { setCards(c); setT0(Date.now()); }).catch(() => onDone()); }, [api, count, onDone]);
  const card = cards?.[0];
  const rate = useCallback(async (correct: boolean) => {
    if (!card) return;
    await api(`/cards/${card.id}/review`, "POST", { correct, elapsed_ms: Date.now() - t0 }).catch(() => {});
    setShown(false); setT0(Date.now());
    setCards((cs) => { const rest = (cs ?? []).slice(1); if (!rest.length) setTimeout(onDone, 0); return rest; });
  }, [api, card, t0, onDone]);
  useEffect(() => { if (cards && cards.length === 0) onDone(); }, [cards, onDone]);
  useLayoutEffect(() => {
    keyRef.current = (e) => {
      if (e.key === " ") { e.preventDefault(); setShown((s) => !s); }
      else if (shown && e.key === "ArrowRight") { e.preventDefault(); void rate(true); }
      else if (shown && e.key === "ArrowLeft") { e.preventDefault(); void rate(false); }
    };
  });
  if (!card) return null;
  return (
    <div className="cards-step">
      <p className="hint">Say the answer before you flip. {cards!.length} to go.</p>
      <button className="flash" onClick={() => setShown((s) => !s)}>
        <span className="kind">{card.kind}</span><span className="front">{card.kind === "your rule" ? card.front : <MathText text={card.front} />}</span>
        {shown ? <span className="back">{card.kind === "your rule" ? card.back : <MathText text={card.back} />}</span> : <span className="hint">Space to flip</span>}
      </button>
      {shown && <div className="row"><button className="go" onClick={() => rate(true)}>Knew it →</button><button className="ghost" onClick={() => rate(false)}>← Missed it</button></div>}
    </div>
  );
}

function Debrief({ api, sessionId }: { api: ReturnType<typeof useSession>["api"]; sessionId: string }) {
  const router = useRouter();
  const [s, setS] = useState<Summary | null>(null);
  const [useful, setUseful] = useState(0);
  const [recall, setRecall] = useState("");
  useEffect(() => { api<Summary>(`/sessions/${sessionId}/summary`).then(setS).catch(() => {}); }, [api, sessionId]);
  async function finish() {
    await api(`/sessions/${sessionId}/end`, "POST", { usefulness: useful || null }).catch(() => {});
    router.push("/today/");
  }
  if (!s) return <p className="sub">Wrapping up…</p>;
  const own = s.correct;
  return (
    <div className="debrief">
      <span className="eyebrow">Session done</span>
      <h2>{s.answered ? `${own} of ${s.answered} on your own.` : "Nicely done."}{s.fixes.length ? ` ${s.fixes.length} fix${s.fixes.length > 1 ? "es" : ""} saved.` : ""}</h2>
      <div className="stats">
        <div className="stat"><b>{s.answered}</b><span>questions answered</span></div>
        <div className="stat"><b>{s.sure_wrong}</b><span>sure but wrong, caught. These are the valuable ones</span></div>
        <div className="stat"><b>{s.next_due ? shortDate(s.next_due) : "–"}</b><span>next check on your fixes</span></div>
      </div>
      {s.fixes.some((f) => f.rule) && (
        <div className="panel"><b>Your rules from today</b>{s.fixes.filter((f) => f.rule).map((f) => <span key={f.id} className="cue">{f.rule}</span>)}</div>
      )}
      <label className="field">Before you go: what&apos;s one thing you&apos;ll remember? <span className="hint">(just for you, saying it fixes it)</span>
        <textarea id="recall" rows={2} value={recall} onChange={(e) => setRecall(e.target.value)} />
      </label>
      <div className="row">
        <span className="hint">How useful was this?</span>
        <div className="seg" role="group" aria-label="Usefulness">{[1, 2, 3, 4, 5].map((n) => <button key={n} aria-pressed={useful === n} onClick={() => setUseful(n)}>{n}</button>)}</div>
      </div>
      <div className="row"><button className="go" onClick={finish}>Finish</button></div>
    </div>
  );
}

function Runner() {
  const { api, me } = useSession();
  const params = useSearchParams();
  const router = useRouter();
  const [plan, setPlan] = useState<GuidedPlan | null>(null);
  const [idx, setIdx] = useState(0);
  const [items, setItems] = useState<Record<string, Item>>({});
  const [extra, setExtra] = useState<Item | null>(null);
  const [tax, setTax] = useState<Taxonomy | null>(null);
  const [skills, setSkills] = useState<SkillMap>({});
  const [stats, setStats] = useState<Stats | null>(null);
  const [showWhy, setShowWhy] = useState(false);
  const [error, setError] = useState("");
  const keyRef = useRef<((e: KeyboardEvent) => void) | null>(null);
  const started = useRef(false);

  useEffect(() => {
    if (!me || started.current) return;
    started.current = true;
    const id = params.get("id");
    const load = id
      ? api<GuidedPlan>(`/sessions/${id}`)
      : api<GuidedPlan>("/sessions/start", "POST", {
        minutes: Number(params.get("minutes") || 45), section: params.get("section") || null, only_skill: params.get("only_skill") || null,
      });
    load.then((p) => {
      setPlan(p);
      if (!id) router.replace(`/session/?id=${p.id}`);
      const done = new Set(p.done_items ?? []);
      const resumeAt = p.steps.findIndex((s, i) => s.item_id ? !done.has(s.item_id) : p.steps.slice(i + 1).some((x) => x.item_id && !done.has(x.item_id)));
      setIdx(id ? (resumeAt < 0 ? p.steps.length : resumeAt) : 0);
    }).catch((e) => setError(e.message));
    api<Taxonomy>("/taxonomy").then(setTax).catch(() => {});
    api<SkillMap>("/skills").then(setSkills).catch(() => {});
    api<Stats>("/stats").then(setStats).catch(() => {});
  }, [api, me, params, router]);

  const step = plan?.steps[idx];
  useEffect(() => {
    if (!step?.item_id || step.kind === "worked" || items[step.item_id]) return;
    api<Item>(`/items/${step.item_id}`).then((it) => setItems((m) => ({ ...m, [it.id]: it }))).catch(() => setIdx((i) => i + 1));
  }, [api, step, items]);

  const next = useCallback(() => { setExtra(null); setShowWhy(false); setIdx((i) => i + 1); }, []);
  const similar = useCallback(async () => {
    if (!step?.skill_id) return;
    try { setExtra(await api<Item>(`/items/next?skill_id=${encodeURIComponent(step.skill_id)}&allow_seen=true`)); } catch { /* none left */ }
  }, [api, step]);
  const onKey = useCallback((e: KeyboardEvent) => keyRef.current?.(e), []);

  const total = plan?.steps.length ?? 0;
  const block = plan?.blocks.find((b) => b.key === step?.block);
  const segs = useMemo(() => plan?.steps.map((s, i) => ({ i, block: s.block })) ?? [], [plan]);
  const item = extra ?? (step?.item_id ? items[step.item_id] : undefined);
  const sk = item?.skill_id ? skills[item.skill_id] : undefined;
  const tip = item && !tipFaded(stats?.skills[item.skill_id ?? ""]) ? tipFor(item.skill_id) : null;
  // In the mixed set the type isn't announced: recognizing it is the skill. Hidden proofs stay unlabeled too.
  const unlabeled = step?.block === "mixed";

  return (
    <Shell me={me} api={api} onKey={onKey}>
      <div className="view session">
        {plan && idx < total && (
          <header className="run-head">
            <div className="progress" aria-label={`Step ${idx + 1} of ${total}`}>
              {segs.map((s) => <i key={s.i} className={`b-${s.block} ${s.i < idx ? "done" : s.i === idx ? "now" : ""}`} />)}
            </div>
            <div className="row spread">
              <span><b>{block?.title ?? "Practice"}</b> <span className="hint">· {idx + 1} of {total}</span></span>
              <button className="link" onClick={() => setShowWhy((w) => !w)} aria-expanded={showWhy}>Why this?</button>
            </div>
            {showWhy && <p className="why-note">{WHY[step?.block ?? ""] ?? block?.why}</p>}
          </header>
        )}
        {error && <p className="err" role="alert">{error}</p>}
        {!plan && !error && <p className="sub">Planning your session…</p>}

        {plan && step?.kind === "cards" && <CardsStep key={idx} api={api} count={step.count ?? 5} onDone={next} keyRef={keyRef} />}
        {plan && step?.kind === "worked" && <WorkedStep key={idx} api={api} step={step} sessionId={plan.id} onDone={next} keyRef={keyRef} />}
        {plan && step && (step.kind === "question" || step.kind === "reattempt") && item && (
          <QuestionCard
            key={`${idx}-${item.id}`} api={api} item={item} tax={tax} sessionId={plan.id}
            flags={extra ? {} : step.flags} section={sk?.section ?? plan.section}
            skillName={unlabeled && !extra ? (sk ? DOMAIN[sk.domain] : undefined) : sk?.name}
            tip={unlabeled && !extra ? null : tip}
            reason={extra ? "Similar question · practice" : step.kind === "reattempt" ? "Seen before · from your log" : unlabeled ? undefined : step.reason}
            ruleHint={step.kind === "reattempt" || (step.ticket_id && step.block === "warmup") ? step.rule ?? null : null}
            onDone={next} onSimilar={extra ? undefined : similar} onKeyRef={keyRef}
          />
        )}
        {plan && idx >= total && <Debrief api={api} sessionId={plan.id} />}
      </div>
    </Shell>
  );
}

export default function Page() {
  return <Suspense><Runner /></Suspense>;
}
