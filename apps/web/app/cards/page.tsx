"use client";
import { useCallback, useEffect, useState } from "react";
import MathText from "@/components/MathText";
import Shell from "@/components/Shell";
import { useSession } from "@/lib/me";
import type { Card } from "@/lib/types";

// Five-minute rule reps. Space flips; right arrow = knew it, left = missed it. The schedule comes from what
// she does and how long it took, never from a self-rating.
export default function Cards() {
  const { api, me } = useSession();
  const [cards, setCards] = useState<Card[] | null>(null);
  const [shown, setShown] = useState(false);
  const [t0, setT0] = useState(0);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api<Card[]>("/cards/due").then((c) => { setCards(c); setShown(false); setT0(Date.now()); }).catch((e) => setError(e.message));
  }, [api]);
  useEffect(() => { if (me) load(); }, [me, load]);

  const card = cards?.[0];
  const rate = useCallback(async (correct: boolean) => {
    if (!card) return;
    try {
      await api(`/cards/${card.id}/review`, "POST", { correct, elapsed_ms: Date.now() - t0 });
      setCards((cs) => (cs ?? []).slice(1)); setShown(false); setT0(Date.now());
    } catch (e) { setError(e instanceof Error ? e.message : "That didn't save."); }
  }, [api, card, t0]);

  const onKey = useCallback((e: KeyboardEvent) => {
    if (!card) return;
    if (e.key === " ") { e.preventDefault(); setShown((s) => !s); }
    else if (shown && e.key === "ArrowRight") { e.preventDefault(); void rate(true); }
    else if (shown && e.key === "ArrowLeft") { e.preventDefault(); void rate(false); }
  }, [card, shown, rate]);

  return (
    <Shell me={me} api={api} onKey={onKey}>
      <div className="view" style={{ maxWidth: 720 }}>
        <div className="row spread"><h1 className="title">Cards</h1>{cards && cards.length > 0 && <span className="hint">{cards.length} due</span>}</div>
        {error && <p className="err" role="alert">{error}</p>}
        {cards && !card && <p className="sub">You&apos;re caught up. Nice.</p>}
        {card && (
          <>
            <button className="flash" onClick={() => setShown((s) => !s)} aria-label="Flip card">
              <span className="kind">{card.kind}</span>
              <span className="front">{card.kind === "your rule" ? card.front : <MathText text={card.front} />}</span>
              {shown ? <span className="back">{card.kind === "your rule" ? card.back : <MathText text={card.back} />}</span> : <span className="hint">Space to flip</span>}
            </button>
            {shown ? (
              <div className="row">
                <button className="go" onClick={() => rate(true)}>Knew it →</button>
                <button className="ghost" onClick={() => rate(false)}>← Missed it</button>
              </div>
            ) : <div className="row"><button className="go" onClick={() => setShown(true)}>Show answer</button></div>}
          </>
        )}
      </div>
    </Shell>
  );
}
