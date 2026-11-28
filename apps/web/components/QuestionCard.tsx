"use client";
import { useCallback, useEffect, useLayoutEffect, useMemo, useState } from "react";
import MathText from "@/components/MathText";
import PaceRing from "@/components/PaceRing";
import Solved, { Html } from "@/components/Solved";
import type { Api } from "@/lib/api";
import { ASK, CATEGORY, paceSeconds, WHY, type Tip } from "@/lib/coach";
import { validateEntry } from "@/lib/entry";
import { NEEDS_PATTERN, shortDate } from "@/lib/format";
import type { AttemptResult, Diagnosis, Item, MicroSkill, Solved as SolvedItem, Taxonomy } from "@/lib/types";

// One question, start to finish: answer, how sure, check; a miss gets one more look before anything is
// revealed; then the explanation, a question about what happened (ask, don't label), an optional one-line
// rule, and a saved fix. Everything works from the keyboard.
type Phase = "answer" | "retry" | "reveal" | "saved";
const CONF = [["sure", "S", "ure"], ["unsure", "U", "nsure"], ["guess", "G", "uess"]] as const;
const LETTERS = ["A", "B", "C", "D"];

export type Outcome = { correct: boolean | null; sureWrong: boolean; fixSaved: boolean };

function friendly(reasons: string[], recheck: boolean): string {
  const say: [RegExp, string][] = [
    [/intermediate value/, "Your first answer was a step along the way."],
    [/Desmos was used/, "Desmos was in the mix the first time."],
    [/time was over p90/, "You knew it, but it took a while."],
    [/^cold retry right untimed/, "You knew it without the clock, so it's a slip, not a gap."],
    [/distractor or evidence/, "Wrong twice on a reading question usually means a convincing wrong answer."],
    [/content or setup gap/, "Wrong twice usually means there's something to learn here."],
    [/provisional/, "You went straight to the solution, so this is Peak's best guess."],
  ];
  const out = reasons.map((r) => say.find(([re]) => re.test(r))?.[1]).filter(Boolean) as string[];
  if (recheck) out.push("You were sure the first time. Those are the most valuable misses to catch, so it comes back at 2 days and a week.");
  return out.join(" ");
}

export default function QuestionCard({
  api, item, tax, sessionId, flags, section, skillName, tip, reason, ruleHint, onDone, onSimilar, onKeyRef,
}: {
  api: Api; item: Item; tax: Taxonomy | null; sessionId?: string; flags?: Record<string, unknown>;
  section?: string; skillName?: string; tip?: Tip | null; reason?: string; ruleHint?: string | null;
  onDone: (o: Outcome) => void; onSimilar?: () => void;
  onKeyRef: { current: ((e: KeyboardEvent) => void) | null };
}) {
  const [phase, setPhase] = useState<Phase>("answer");
  const [answer, setAnswer] = useState("");
  const [conf, setConf] = useState("");
  const [first, setFirst] = useState<{ answer: string; result: AttemptResult } | null>(null);
  const [result, setResult] = useState<AttemptResult | null>(null);
  const [diag, setDiag] = useState<Diagnosis | null>(null);
  const [cause, setCause] = useState("");
  const [micro, setMicro] = useState("");
  const [askOpen, setAskOpen] = useState(false);
  const [rule, setRule] = useState("");
  const [example, setExample] = useState<SolvedItem | null>(null);
  const [assisted, setAssisted] = useState(false);
  const [started, setStarted] = useState(() => Date.now());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [savedCue, setSavedCue] = useState<string | null>(null);
  const [tipOpen, setTipOpen] = useState(!!tip);
  const [retryOn, setRetryOn] = useState("");

  useEffect(() => { setStarted(Date.now()); }, [item.id]);

  const entryError = useMemo(() => {
    if (item.format !== "numeric" || !answer) return "";
    const r = validateEntry(answer);
    return r.ok ? "" : r.reason;
  }, [item, answer]);

  const missed = first !== null && first.result.correct !== true;
  const patterns: MicroSkill[] = (tax?.micro_skills ?? []).filter((m) => m.cause === cause);
  const canSave = !!cause && (!NEEDS_PATTERN.has(cause) || !!micro);
  const category = CATEGORY.find(([k]) => k === cause);

  const submit = useCallback(async (skip = false) => {
    if (busy) return;
    if (phase === "answer" && (!answer || !conf || entryError)) return;
    if (phase === "retry" && !skip && (!answer || entryError)) return;
    setBusy(true); setError("");
    try {
      const r = await api<AttemptResult>("/attempts", "POST", {
        item_id: item.id, idempotency_key: crypto.randomUUID(), answer: skip ? null : answer, session_id: sessionId ?? null,
        confidence: phase === "answer" ? conf : null, elapsed_ms: Date.now() - started,
        flags: { ...(flags ?? {}), ...(assisted ? { aided: true } : {}), ...(phase === "retry" ? { cold_retry: true } : {}) },
      });
      if (phase === "answer") {
        setFirst({ answer, result: r });
        if (r.revealed) { setResult(r); setPhase("reveal"); }
        else { setPhase("retry"); setAnswer(""); }
      } else {
        setResult(r);
        const d = await api<Diagnosis>(`/attempts/${first!.result.attempt_id}/diagnose`, "POST", { cold_retry_correct: r.correct === true });
        setDiag(d);
        const c = d.cause === "tool_misuse" ? "setup_method" : d.cause === "entry" ? "execution" : d.cause ?? "content_gap";
        setCause(c);
        setPhase("reveal");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "That didn't go through. Try again.");
    } finally { setBusy(false); }
  }, [api, item.id, busy, phase, answer, conf, entryError, started, first, sessionId, flags, assisted]);

  const save = useCallback(async () => {
    if (!first || !canSave || busy) return;
    setBusy(true); setError("");
    try {
      const t = await api<{ id: string; cue: string | null }>(`/attempts/${first.result.attempt_id}/ticket`, "POST",
        { cause, micro_skill: micro || null, rule: rule.trim() || null });
      setSavedCue(t.cue);
      setRetryOn(shortDate(new Date(Date.now() + 2 * 864e5).toISOString()));
      // Seeing the explanation is the repair, so the fix goes straight to its first spaced re-attempt.
      await api(`/tickets/${t.id}/repair/start`, "POST", { intervention: "explanation" }).catch(() => {});
      await api(`/tickets/${t.id}/repair/complete`, "POST").catch(() => {});
      setPhase("saved");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't save the fix.");
    } finally { setBusy(false); }
  }, [api, first, canSave, busy, cause, micro, rule]);

  const finish = useCallback(() => {
    onDone({ correct: first?.result.correct ?? null, sureWrong: missed && conf === "sure", fixSaved: phase === "saved" });
  }, [onDone, first, missed, conf, phase]);

  async function showExample() {
    if (!item.skill_id || busy) return;
    setBusy(true);
    try {
      const ex = await api<SolvedItem>(`/skills/${item.skill_id}/example`, "POST", { idempotency_key: `ex-${item.id}`, session_id: sessionId ?? null });
      setExample(ex); setAssisted(true);
    } catch { setError("No solved example is left for this skill."); }
    finally { setBusy(false); }
  }

  // Keyboard: A-D, S/U/G, Return. Handed to the page's single key listener after each commit.
  const handleKey = (e: KeyboardEvent) => {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    const tag = (e.target as HTMLElement)?.tagName;
    const typing = tag === "INPUT" || tag === "TEXTAREA";
    const k = e.key.toLowerCase();
    if (!typing && item.format === "mc" && (phase === "answer" || phase === "retry") && LETTERS.includes(k.toUpperCase()) && k.length === 1) {
      const L = k.toUpperCase();
      if (!(phase === "retry" && first?.answer === L) && item.choices?.[L] !== undefined) setAnswer(L);
      e.preventDefault(); return;
    }
    const c = ({ s: "sure", u: "unsure", g: "guess" } as Record<string, string>)[k];
    if (!typing && phase === "answer" && c) { setConf(c); e.preventDefault(); return; }
    if (k === "enter" && !(tag === "TEXTAREA")) {
      e.preventDefault();
      if (phase === "answer" || phase === "retry") void submit();
      else if (phase === "reveal" && missed) void save();
      else finish();
    }
  };
  useLayoutEffect(() => { onKeyRef.current = handleKey; });

  const revealed = phase === "reveal" || phase === "saved";
  function choice(L: string, html: string) {
    const key = result?.key ?? [];
    let cls = "choice";
    if (phase === "retry" && first?.answer === L) cls += " first-miss dim";
    if (revealed) cls += key.includes(L) ? " right" : first?.answer === L ? " first-miss yours" : " dim";
    return (
      <button key={L} className={cls} aria-pressed={!revealed && answer === L} disabled={revealed || (phase === "retry" && first?.answer === L)} onClick={() => setAnswer(L)}>
        <span className="L">{L}</span><Html html={html} />
        {revealed && first?.answer === L && !key.includes(L) && <span className="tag">Your answer</span>}
        {revealed && key.includes(L) && <span className="tag ok">Correct</span>}
      </button>
    );
  }

  const question = (
    <div className="q-col">
      <Html html={item.stem} className="stem" />
      {item.format === "mc" && item.choices ? (
        <div className="choices" role="group" aria-label="Answer choices">{Object.entries(item.choices).map(([L, h]) => choice(L, h))}</div>
      ) : (phase === "answer" || phase === "retry") ? (
        <label className="numeric">Your answer
          <input id="numeric-answer" autoFocus inputMode="decimal" autoComplete="off" value={answer} onChange={(e) => setAnswer(e.target.value)} aria-invalid={!!entryError} />
          {entryError && <span className="hint err" role="alert">{entryError}</span>}
        </label>
      ) : (
        <div className="numeric-result">
          {first && <span className={first.result.correct ? "ok" : "miss"}>Your answer: <b>{first.answer}</b></span>}
          <span className="ok">Correct: <b>{result?.key?.join(" or ")}</b></span>
        </div>
      )}
    </div>
  );

  return (
    <div className="qcard">
      <div className="q-meta">
        {skillName && <span className="pill">{skillName}</span>}
        {item.difficulty && <span className="pill">{item.difficulty[0].toUpperCase() + item.difficulty.slice(1)}</span>}
        {item.seen_before && <span className="pill warn">Seen before · practice only</span>}
        {reason && <span className="reason">{reason}</span>}
        <span className="spacer" />
        <PaceRing start={started} target={paceSeconds(section)} running={phase === "answer"} />
      </div>

      {ruleHint && phase !== "saved" && <div className="cue">Your rule: {ruleHint}</div>}
      {tip && phase === "answer" && (
        <div className={`tip ${tipOpen ? "" : "closed"}`}>
          <button className="tip-head" onClick={() => setTipOpen((o) => !o)} aria-expanded={tipOpen}><span className="spark" />Strategy</button>
          {tipOpen && <div className="tip-body"><MathText text={tip.how} /><span className="trap">Watch for: <MathText text={tip.trap} /></span></div>}
        </div>
      )}

      {item.passage ? <div className="q-grid split"><Html html={item.passage} className="passage" />{question}</div> : <div className="q-grid">{question}</div>}
      {error && <p className="err" role="alert">{error}</p>}

      {example && phase !== "saved" && (
        <details className="example" open>
          <summary>A solved one like it <span className="hint">· this question now counts as practice with help</span></summary>
          <Solved item={example} compact />
        </details>
      )}

      {phase === "answer" && (
        <div className="actions">
          <div className="conf" role="group" aria-label="How sure are you?">
            <span title={WHY.confidence}>How sure?</span>
            {CONF.map(([k, key, rest]) => <button key={k} aria-pressed={conf === k} onClick={() => setConf(k)}><u>{key}</u>{rest}</button>)}
          </div>
          <div className="row">
            <button className="go" onClick={() => submit()} disabled={!answer || !conf || !!entryError || busy}>Check answer</button>
            {!example && item.skill_id && <button className="ghost" onClick={showExample} disabled={busy}>Show an example</button>}
            <span className="hint">{!answer ? (item.format === "mc" ? "A, B, C or D" : "Type your answer") : !conf ? "How sure? S, U or G" : "Return to check"}</span>
          </div>
        </div>
      )}

      {phase === "retry" && (
        <div className="actions">
          <div className="note retry"><b>Not quite. One more look, no clock.</b><span>{item.format === "mc" ? "Your first answer is dimmed." : `Your first answer was ${first?.answer}.`} The explanation stays hidden until you try again.</span></div>
          <div className="row">
            <button className="go" onClick={() => submit()} disabled={!answer || !!entryError || busy}>Check again</button>
            <button className="ghost" onClick={() => submit(true)} disabled={busy}>Show me the solution</button>
          </div>
        </div>
      )}

      {revealed && result && (
        <div className="review">
          {!missed && conf === "guess" && <div className="note info"><b>Right, but you guessed.</b><span>No credit for a guess. Peak will bring this kind back soon.</span></div>}
          {!missed && conf !== "guess" && <div className="note good"><b>{assisted ? "Right, with help." : "Clean."}</b><span>{assisted ? "It counts as practice. The next one is on your own." : conf === "sure" ? "Right and sure. That one counts." : "Right. Next time, trust it a little more."}</span></div>}
          {missed && <div className={`note ${result.correct ? "good" : "retry"}`}><b>{result.correct ? "Got it on the second look." : `The answer is ${result.key?.join(" or ")}.`}</b></div>}
          {result.rationale && <div className="explain"><span className="kind">Why</span><Html html={result.rationale} /></div>}

          {missed && phase === "reveal" && diag && (
            <div className="name-it">
              <b className="ask">{category ? `Looks like ${category[3]}. ${patterns.length ? "Which one?" : "Fair?"}` : "What happened?"}</b>
              <span className="hint">{friendly(diag.reasons, diag.reverify_days.length > 0)}</span>
              {patterns.length > 0 && (
                <div className="chips" role="group" aria-label="Pattern">
                  {patterns.map((m) => <button key={m.key} aria-pressed={micro === m.key} title={ASK[m.key]} onClick={() => setMicro(micro === m.key ? "" : m.key)}>{m.label}</button>)}
                </div>
              )}
              {!askOpen ? (
                <button className="link" onClick={() => setAskOpen(true)}>Something else happened</button>
              ) : (
                <div className="chips" role="group" aria-label="What happened">
                  {CATEGORY.map(([k, label, hint]) => <button key={k} title={hint} aria-pressed={cause === k} onClick={() => { setCause(k); setMicro(""); }}>{label}</button>)}
                </div>
              )}
              <label className="field rule" title={WHY.rule}>Your rule, in one line <span className="hint">(optional, it becomes one of your cards)</span>
                <input id="fix-rule" maxLength={200} value={rule} onChange={(e) => setRule(e.target.value)} placeholder="e.g. Percent change divides by the original, not the new" />
              </label>
              <div className="row">
                <button className="go" onClick={save} disabled={!canSave || busy}>Save the fix</button>
                {onSimilar && <button className="ghost" onClick={onSimilar}>Try a similar question</button>}
                <span className="hint">{canSave ? "Return to save" : "Pick the pattern. “Careless” always has a name."}</span>
              </div>
            </div>
          )}

          {phase === "saved" && (
            <div className="note info"><b>Fix saved.</b><span>{savedCue ? `You'll see “${savedCue}” on questions like this. ` : ""}{rule.trim() ? "Your rule is now a card. " : ""}First re-attempt on {retryOn}, then a fresh one a week later.</span></div>
          )}
          {(!missed || phase === "saved") && (
            <div className="row">
              <button className="go" onClick={finish}>Next</button>
              {onSimilar && phase !== "saved" && <button className="ghost" onClick={onSimilar}>Try a similar question</button>}
              <span className="hint">Return</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
