"use client";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import Shell from "@/components/Shell";
import { useSession } from "@/lib/me";
import { validateEntry } from "@/lib/entry";
import type { AttemptResult, Diagnosis, Item, MicroSkill } from "@/lib/types";

type Phase = "answer" | "retry" | "review" | "diagnose" | "done" | "empty";
const CONF = [["sure", "Sure"], ["unsure", "Unsure"], ["guess", "Guess"]] as const;

function Html({ html }: { html: string | null }) {
  // The API sanitizes with an allowlist before storage; this renders that safe subset.
  return html ? <div className="stem" dangerouslySetInnerHTML={{ __html: html }} /> : null;
}

function Practice() {
  const { api, me } = useSession();
  const skill = useSearchParams().get("skill");
  const [item, setItem] = useState<Item | null>(null);
  const [phase, setPhase] = useState<Phase>("answer");
  const [answer, setAnswer] = useState("");
  const [conf, setConf] = useState<string>("");
  const [started, setStarted] = useState(0);
  const [first, setFirst] = useState<AttemptResult | null>(null);
  const [result, setResult] = useState<AttemptResult | null>(null);
  const [diag, setDiag] = useState<Diagnosis | null>(null);
  const [micro, setMicro] = useState<MicroSkill[]>([]);
  const [cause, setCause] = useState("");
  const [microKey, setMicroKey] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [fallback, setFallback] = useState(false);

  const load = useCallback(async () => {
    setError(""); setAnswer(""); setConf(""); setFirst(null); setResult(null); setDiag(null); setFallback(false);
    try {
      let it: Item;
      try {
        it = await api<Item>(`/items/next${skill ? `?skill_id=${encodeURIComponent(skill)}` : ""}`);
      } catch (e) {
        if (!skill) throw e;
        // The focus skill has no fresh item left: say so, then take the next-best fresh item.
        it = await api<Item>("/items/next");
        setFallback(true);
      }
      setItem(it); setPhase("answer"); setStarted(Date.now());
    } catch (e) {
      setItem(null); setPhase("empty"); setError(e instanceof Error ? e.message : "No item");
    }
  }, [api, skill]);

  useEffect(() => { if (me) void load(); }, [me, load]);
  useEffect(() => { api<{ micro_skills: MicroSkill[] }>("/taxonomy").then((t) => setMicro(t.micro_skills)).catch(() => {}); }, [api]);

  const entryError = useMemo(() => {
    if (item?.format !== "numeric" || !answer) return "";
    const r = validateEntry(answer);
    return r.ok ? "" : r.reason;
  }, [item, answer]);

  async function submit(skip = false) {
    if (!item) return;
    setBusy(true); setError("");
    try {
      const r = await api<AttemptResult>("/attempts", "POST", {
        item_id: item.id,
        idempotency_key: crypto.randomUUID(),
        answer: skip ? null : answer,
        confidence: phase === "answer" ? conf || null : null,
        elapsed_ms: Date.now() - started,
        flags: phase === "retry" ? { cold_retry: true } : {},
      });
      if (phase === "answer") {
        setFirst(r);
        if (r.correct === true) { setResult(r); setPhase("review"); }
        else if (r.needs_cold_retry) { setPhase("retry"); setAnswer(""); setStarted(Date.now()); }
        else { setResult(r); setPhase("review"); }
      } else {
        setResult(r); setPhase("review");
        if (first && first.correct !== true) {
          const d = await api<Diagnosis>(`/attempts/${first.attempt_id}/diagnose`, "POST", { cold_retry_correct: r.correct === true });
          setDiag(d); setCause(d.cause ?? "");
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not submit");
    } finally { setBusy(false); }
  }

  async function makeTicket() {
    if (!first) return;
    setBusy(true); setError("");
    try {
      await api(`/attempts/${first.attempt_id}/ticket`, "POST", { cause, micro_skill: microKey || null });
      setPhase("done");
    } catch (e) { setError(e instanceof Error ? e.message : "Could not save"); }
    finally { setBusy(false); }
  }

  const picker = item && (
    <>
      {item.format === "mc" && item.choices ? (
        <div className="row" style={{ display: "grid", gap: 8 }}>
          {Object.entries(item.choices).map(([k, v]) => (
            <button key={k} className="choice" aria-pressed={answer === k} onClick={() => setAnswer(k)}>
              <strong>{k}</strong><span dangerouslySetInnerHTML={{ __html: v }} />
            </button>
          ))}
        </div>
      ) : (
        <label>Your answer
          <input type="text" inputMode="decimal" autoComplete="off" value={answer} onChange={(e) => setAnswer(e.target.value)} aria-invalid={!!entryError} />
          {entryError && <span className="err" role="alert">{entryError}</span>}
        </label>
      )}
    </>
  );

  const canSubmit = !!answer && !entryError && !busy && (phase !== "answer" || !!conf);
  const microForCause = micro.filter((m) => !cause || m.cause === cause);
  return (
    <Shell me={me} api={api}>
      <h1>Practice</h1>
      {error && phase !== "empty" && <p className="err" role="alert">{error}</p>}
      {phase === "empty" && <p className="card">{error.includes("new item") ? "Needs a new item: nothing fresh is left for this skill, and repeats can't count as proof." : error}</p>}
      {fallback && phase === "answer" && <p className="banner">No fresh question is left for today&apos;s focus skill, so here&apos;s the next best one. Repeats can&apos;t count as proof.</p>}
      {item && (phase === "answer" || phase === "retry") && (
        <section className="card">
          {phase === "retry" && <p className="banner">Not quite. Try once more, no clock, before you see the solution.</p>}
          <Html html={item.passage} />
          <Html html={item.stem} />
          {picker}
          {phase === "answer" && (
            <div className="row" role="group" aria-label="How sure are you?">
              {CONF.map(([k, label]) => (
                <button key={k} className="chip" aria-pressed={conf === k} onClick={() => setConf(k)}>{label}</button>
              ))}
            </div>
          )}
          <div className="row">
            <button className="btn" disabled={!canSubmit} onClick={() => submit(false)}>Check</button>
            {phase === "retry" && <button className="btn ghost" disabled={busy} onClick={() => submit(true)}>Show me the solution</button>}
          </div>
        </section>
      )}
      {phase === "review" && result && (
        <section className="card" aria-live="polite">
          <h2 className={result.correct ? "ok" : "bad"}>{result.correct ? "Correct" : "Not this time"}</h2>
          {result.key && <p>Answer: <strong>{result.key.join(" or ")}</strong></p>}
          <Html html={result.rationale ?? null} />
          {diag && (
            <div className="banner">
              <strong>Proposed cause: {diag.cause?.replace("_", " ") ?? "none"}</strong>
              <ul>{diag.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
            </div>
          )}
          {diag?.ticket_required ? (
            <>
              <label>What was it, really?
                <select value={cause} onChange={(e) => { setCause(e.target.value); setMicroKey(""); }}>
                  {["content_gap","setup_method","requested_quantity","execution","entry","evidence_distractor","pacing","tool_misuse"].map((c) => <option key={c} value={c}>{c.replace("_", " ")}</option>)}
                </select>
              </label>
              <label>Name the pattern (not &quot;careless&quot;)
                <select value={microKey} onChange={(e) => setMicroKey(e.target.value)}>
                  <option value="">None, it was a content gap</option>
                  {microForCause.map((m) => <option key={m.key} value={m.key}>{m.label}</option>)}
                </select>
              </label>
              <button className="btn" disabled={busy || !cause} onClick={makeTicket}>Make a fix</button>
            </>
          ) : (
            <button className="btn" onClick={load}>Next question</button>
          )}
        </section>
      )}
      {phase === "done" && (
        <section className="card">
          <p className="ok">Fix saved. Peak will check it on a fresh question tomorrow and again in a week.</p>
          <button className="btn" onClick={load}>Next question</button>
        </section>
      )}
    </Shell>
  );
}

export default function Page() {
  return <Suspense><Practice /></Suspense>;
}
