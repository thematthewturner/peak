"use client";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import Shell from "@/components/Shell";
import { useToast } from "@/components/Toast";
import { validateEntry } from "@/lib/entry";
import { CAUSE, DOMAIN, NEEDS_PATTERN } from "@/lib/format";
import { useSession } from "@/lib/me";
import { ApiError } from "@/lib/session";
import type { AttemptResult, Diagnosis, Item, MicroSkill, SkillMap, Taxonomy } from "@/lib/types";

// The core loop: answer, say how sure, check; a miss gets one more look before the answer shows;
// then understand it and name it in two taps. Every step works from the keyboard.
type Phase = "loading" | "answer" | "retry" | "reveal" | "saved" | "empty";
const CONF = [["sure", "S", "ure"], ["unsure", "U", "nsure"], ["guess", "G", "uess"]] as const;
const LETTERS = ["A", "B", "C", "D"];

// The engine's reasons, said the way a friend would say them.
const SAY: [RegExp, string][] = [
  [/^sure \+ wrong/, ""],
  [/answer matches an intermediate value/, "Your first answer was a step along the way. Re-read what the question asks for."],
  [/Desmos was used/, "Desmos was in the mix the first time."],
  [/time was over p90/, "You knew it, but it took longer than usual."],
  [/^cold retry right untimed/, "You knew it without the clock, so it's a slip, not a gap."],
  [/distractor or evidence/, "Wrong twice on a reading question usually means a convincing wrong answer pulled you in."],
  [/content or setup gap/, "Wrong twice usually means there's something to learn here, not a slip."],
  [/provisional/, "You went straight to the solution, so this is Peak's best guess."],
];
function friendly(reasons: string[], recheck: boolean): string {
  const said = reasons.map((r) => SAY.find(([re]) => re.test(r))?.[1]).filter(Boolean) as string[];
  if (recheck) said.push("You were sure the first time, so this one gets checked again in 2 and 7 days.");
  return said.join(" ");
}

function Html({ html, className = "" }: { html: string | null | undefined; className?: string }) {
  // Item HTML is sanitized to an allowlist when it is imported; this renders that safe subset.
  return html ? <div className={`html ${className}`} dangerouslySetInnerHTML={{ __html: html }} /> : null;
}

function Practice() {
  const { api, me } = useSession();
  const skill = useSearchParams().get("skill");
  const { toast, node: toastNode } = useToast();
  const [item, setItem] = useState<Item | null>(null);
  const [phase, setPhase] = useState<Phase>("loading");
  const [answer, setAnswer] = useState("");
  const [conf, setConf] = useState<string>("");
  const [first, setFirst] = useState<{ answer: string; result: AttemptResult } | null>(null);
  const [result, setResult] = useState<AttemptResult | null>(null);
  const [retryAnswer, setRetryAnswer] = useState<string | null>(null);
  const [diag, setDiag] = useState<Diagnosis | null>(null);
  const [cause, setCause] = useState("");
  const [micro, setMicro] = useState("");
  const [tax, setTax] = useState<Taxonomy | null>(null);
  const [skills, setSkills] = useState<SkillMap>({});
  const [fallback, setFallback] = useState(false);
  const [count, setCount] = useState(0);
  const [started, setStarted] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [savedCue, setSavedCue] = useState<string | null>(null);
  const [emptyBank, setEmptyBank] = useState(false);

  const load = useCallback(async () => {
    setPhase("loading"); setAnswer(""); setConf(""); setFirst(null); setResult(null); setRetryAnswer(null);
    setDiag(null); setCause(""); setMicro(""); setError(""); setFallback(false); setSavedCue(null);
    try {
      let it: Item;
      try {
        it = await api<Item>(`/items/next${skill ? `?skill_id=${encodeURIComponent(skill)}` : ""}`);
      } catch (e) {
        if (!skill) throw e;
        it = await api<Item>("/items/next"); // focus skill is out of fresh questions: say so, keep going
        setFallback(true);
      }
      setItem(it); setPhase("answer"); setStarted(Date.now()); setCount((c) => c + 1);
    } catch (e) {
      setItem(null);
      if (e instanceof ApiError && e.status === 404) {
        // Tell "nothing loaded yet" apart from "everything already seen".
        const b = await api<{ ready: number; seen: number }>("/bank").catch(() => null);
        setEmptyBank(!!b && b.ready === 0);
        setPhase("empty");
      } else {
        setError(e instanceof Error ? `Couldn't load a question: ${e.message}` : "Couldn't load a question.");
        setPhase("empty"); setEmptyBank(false);
      }
    }
  }, [api, skill]);

  useEffect(() => { if (me) void load(); }, [me, load]);
  useEffect(() => {
    if (!me) return;
    api<Taxonomy>("/taxonomy").then(setTax).catch(() => {});
    api<SkillMap>("/skills").then(setSkills).catch(() => {});
  }, [api, me]);

  const entryError = useMemo(() => {
    if (item?.format !== "numeric" || !answer) return "";
    const r = validateEntry(answer);
    return r.ok ? "" : r.reason;
  }, [item, answer]);

  const missed = first !== null && first.result.correct !== true;
  const patterns: MicroSkill[] = (tax?.micro_skills ?? []).filter((m) => m.cause === cause);
  const canSave = !!cause && (!NEEDS_PATTERN.has(cause) || !!micro);

  const submit = useCallback(async (skip = false) => {
    if (!item || busy) return;
    if (phase === "answer" && (!answer || !conf || entryError)) return;
    if (phase === "retry" && !skip && (!answer || entryError)) return;
    setBusy(true); setError("");
    try {
      const r = await api<AttemptResult>("/attempts", "POST", {
        item_id: item.id, idempotency_key: crypto.randomUUID(), answer: skip ? null : answer,
        confidence: phase === "answer" ? conf : null, elapsed_ms: Date.now() - started,
        flags: phase === "retry" ? { cold_retry: true } : {},
      });
      if (phase === "answer") {
        setFirst({ answer, result: r });
        if (r.revealed) { setResult(r); setPhase("reveal"); }
        else { setPhase("retry"); setAnswer(""); setStarted(Date.now()); }
      } else {
        setRetryAnswer(skip ? null : answer);
        setResult(r);
        const d = await api<Diagnosis>(`/attempts/${first!.result.attempt_id}/diagnose`, "POST", { cold_retry_correct: r.correct === true });
        setDiag(d);
        setCause(d.cause ?? "content_gap");
        setPhase("reveal");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "That didn't go through. Try again.");
    } finally { setBusy(false); }
  }, [api, item, busy, phase, answer, conf, entryError, started, first]);

  const save = useCallback(async () => {
    if (!first || !canSave || busy) return;
    setBusy(true); setError("");
    try {
      const t = await api<{ id: string; cue: string | null }>(`/attempts/${first.result.attempt_id}/ticket`, "POST", { cause, micro_skill: micro || null });
      setSavedCue(t.cue);
      // Seeing the explanation is the repair, so the fix goes straight to "retry tomorrow".
      await api(`/tickets/${t.id}/repair/start`, "POST", { intervention: "explanation" }).catch(() => {});
      await api(`/tickets/${t.id}/repair/complete`, "POST").catch(() => {});
      setPhase("saved");
      toast("Fix saved.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't save the fix.");
    } finally { setBusy(false); }
  }, [api, first, canSave, busy, cause, micro, toast]);

  const onKey = useCallback((e: KeyboardEvent) => {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    const typing = (e.target as HTMLElement)?.tagName === "INPUT";
    const k = e.key.toLowerCase();
    if (!typing && item?.format === "mc" && (phase === "answer" || phase === "retry") && LETTERS.includes(k.toUpperCase()) && k.length === 1) {
      const L = k.toUpperCase();
      if (!(phase === "retry" && first?.answer === L) && item.choices?.[L] !== undefined) setAnswer(L);
      e.preventDefault(); return;
    }
    if (!typing && phase === "answer" && ({ s: "sure", u: "unsure", g: "guess" } as Record<string, string>)[k]) {
      setConf(({ s: "sure", u: "unsure", g: "guess" } as Record<string, string>)[k]); e.preventDefault(); return;
    }
    if (k === "enter") {
      e.preventDefault();
      if (phase === "answer" || phase === "retry") void submit();
      else if (phase === "reveal" && missed) void save();
      else if (phase === "reveal" || phase === "saved") void load();
    }
  }, [item, phase, first, missed, submit, save, load]);

  const skillInfo = item?.skill_id ? skills[item.skill_id] : undefined;
  const isRW = skillInfo?.section === "rw" || !!item?.passage;

  function choice(L: string, html: string) {
    const revealed = phase === "reveal" || phase === "saved";
    const key = result?.key ?? [];
    let cls = "choice";
    if (phase === "retry" && first?.answer === L) cls += " first-miss dim";
    if (revealed) cls += key.includes(L) ? " right" : first?.answer === L ? " first-miss dim" : " dim";
    const disabled = revealed || (phase === "retry" && first?.answer === L);
    return (
      <button key={L} className={cls} aria-pressed={!revealed && answer === L} disabled={disabled} onClick={() => setAnswer(L)}>
        <span className="L">{L}</span><Html html={html} />
      </button>
    );
  }

  const question = item && (
    <div style={{ display: "grid", gap: 16, alignContent: "start" }}>
      <Html html={item.stem} className="stem" />
      {item.format === "mc" && item.choices ? (
        <div className="choices" role="group" aria-label="Answer choices">{Object.entries(item.choices).map(([L, h]) => choice(L, h))}</div>
      ) : (phase === "answer" || phase === "retry") ? (
        <label className="numeric">Your answer
          <input id="numeric-answer" autoFocus inputMode="decimal" autoComplete="off" value={answer} onChange={(e) => setAnswer(e.target.value)} aria-invalid={!!entryError} />
          {entryError && <span className="hint err" role="alert">{entryError}</span>}
        </label>
      ) : null}
    </div>
  );

  return (
    <Shell me={me} api={api} onKey={onKey}>
      <div className="view" style={{ maxWidth: isRW ? 1100 : 860 }}>
        <div className="row spread"><h1 className="title" style={{ fontSize: 20 }}>Practice</h1>{count > 0 && <span className="hint">Question {count} this session</span>}</div>
        {fallback && phase === "answer" && <p className="banner">No fresh question is left for today&apos;s focus skill, so here&apos;s the next best one. Repeats can&apos;t count as proof.</p>}
        {phase === "empty" && !error && emptyBank && (
          <div className="banner"><b>No questions are loaded yet.</b> Load the question bank from Terminal, then come back:
            <pre style={{ margin: "8px 0 0", whiteSpace: "pre-wrap", fontFamily: "var(--mono)", fontSize: 12.5 }}>cd ~/code/peak/services/backend{"\n"}uv run python -m peak.local import PATH/TO/collegeboard_qbank.jsonl</pre>
          </div>
        )}
        {phase === "empty" && !error && !emptyBank && <p className="banner">You&apos;ve seen every question{skill ? " for this skill" : ""}. Repeats can&apos;t count as proof, so Peak won&apos;t serve one.</p>}
        {item && phase !== "loading" && phase !== "empty" && (
          <>
            <div className="q-meta">
              {skillInfo && <span className="pill">{DOMAIN[skillInfo.domain] ?? skillInfo.domain}</span>}
              {skillInfo && <span className="pill">{skillInfo.name}</span>}
              {item.difficulty && <span className="pill">{item.difficulty[0].toUpperCase() + item.difficulty.slice(1)}</span>}
            </div>
            {item.passage ? (
              <div className="q-grid split"><Html html={item.passage} className="passage" />{question}</div>
            ) : <div className="q-grid">{question}</div>}
          </>
        )}
        {error && <p className="err" role="alert">{error}</p>}

        {phase === "answer" && (
          <>
            <div className="conf" role="group" aria-label="How sure are you?">
              <span>How sure?</span>
              {CONF.map(([k, key, rest]) => <button key={k} aria-pressed={conf === k} onClick={() => setConf(k)}><u>{key}</u>{rest}</button>)}
            </div>
            <div className="row">
              <button className="go" onClick={() => submit()} disabled={!answer || !conf || !!entryError || busy}>Check</button>
              <span className="hint">{!answer ? (item?.format === "mc" ? "Pick an answer: A, B, C or D" : "Type your answer") : !conf ? "Now: how sure? S, U or G" : "Return to check"}</span>
            </div>
          </>
        )}

        {phase === "retry" && (
          <>
            <div className="note retry"><b>Not quite. One more look, no clock.</b><span>{item?.format === "mc" ? "Your first answer is dimmed." : `Your first answer was ${first?.answer}.`} The solution stays hidden until you try again.</span></div>
            <div className="row">
              <button className="go" onClick={() => submit()} disabled={!answer || !!entryError || busy}>Check again</button>
              <button className="ghost" onClick={() => submit(true)} disabled={busy}>Show me the solution</button>
            </div>
          </>
        )}

        {(phase === "reveal" || phase === "saved") && result && (
          <>
            {!missed && conf === "guess" && <div className="note info"><b>Right, but you guessed.</b><span>No credit for a guess. You&apos;ll see this kind of question again soon.</span></div>}
            {!missed && conf !== "guess" && <div className="note good"><b>Clean.</b><span>Right{conf === "sure" ? " and sure" : ""}. That one counts.</span></div>}
            {missed && (
              <div className={`note ${result.correct ? "good" : "retry"}`}>
                <b>{result.correct ? "Got it on the second look." : retryAnswer === null ? `The answer is ${result.key?.join(" or ")}.` : `Still not it. The answer is ${result.key?.join(" or ")}.`}</b>
              </div>
            )}
            <Html html={result.rationale} />
            {missed && phase === "reveal" && diag && (
              <div className="name-it">
                <b style={{ fontSize: 15 }}>What happened?</b>
                <span className="hint">{friendly(diag.reasons, diag.reverify_days.length > 0)}</span>
                <div className="chips" role="group" aria-label="Cause">
                  {Object.entries(CAUSE).map(([k, label]) => <button key={k} aria-pressed={cause === k} onClick={() => { setCause(k); setMicro(""); }}>{label}</button>)}
                </div>
                {patterns.length > 0 && (
                  <div className="chips" role="group" aria-label="Pattern">
                    {patterns.map((m) => <button key={m.key} aria-pressed={micro === m.key} onClick={() => setMicro(micro === m.key ? "" : m.key)}>{m.label}</button>)}
                  </div>
                )}
                {micro && <span className="cue">{patterns.find((m) => m.key === micro)?.cue}</span>}
                <div className="row">
                  <button className="go" onClick={save} disabled={!canSave || busy}>Save the fix</button>
                  <span className="hint">{canSave ? "Return to save" : "Pick the pattern. Careless isn't one."}</span>
                </div>
              </div>
            )}
            {phase === "saved" && (
              <div className="note info" data-testid="fix-saved"><b>Fix saved.</b><span>{savedCue ? `You'll see "${savedCue}" on questions like this. ` : ""}Retry tomorrow, proof in a week on a question you haven't seen.</span></div>
            )}
            {(!missed || phase === "saved") && (
              <div className="row"><button className="go" onClick={load}>Next question</button><span className="hint">Return</span></div>
            )}
          </>
        )}
      </div>
      {toastNode}
    </Shell>
  );
}

export default function Page() {
  return <Suspense><Practice /></Suspense>;
}
