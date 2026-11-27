"use client";
import { useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { useSession } from "@/lib/me";
import type { Card } from "@/lib/types";

export default function Cards() {
  const { api, me } = useSession();
  const [cards, setCards] = useState<Card[] | null>(null);
  const [shown, setShown] = useState(false);
  const [t0, setT0] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    api<Card[]>("/cards/due").then((c) => { setCards(c); setT0(Date.now()); }).catch((e) => setError(e.message));
  }, [api]);

  async function rate(correct: boolean) {
    const card = cards?.[0];
    if (!card) return;
    try {
      // Rating is derived from behavior (right/wrong, time), never self-reported difficulty.
      await api(`/cards/${card.id}/review`, "POST", { correct, elapsed_ms: Date.now() - t0 });
      setCards((cs) => (cs ?? []).slice(1)); setShown(false); setT0(Date.now());
    } catch (e) { setError(e instanceof Error ? e.message : "Failed"); }
  }

  const card = cards?.[0];
  return (
    <Shell me={me} api={api}>
      <h1>Rule cards</h1>
      {error && <p className="err" role="alert">{error}</p>}
      {cards && !card && <p className="card">All caught up. Nice.</p>}
      {card && (
        <section className="card">
          <p className="muted">{card.kind} · {cards?.length} due</p>
          <h2>{card.front}</h2>
          {shown ? <p>{card.back}</p> : <button className="btn" onClick={() => setShown(true)}>Show answer</button>}
          {shown && (
            <div className="row">
              <button className="btn" onClick={() => rate(true)}>I knew it</button>
              <button className="btn ghost" onClick={() => rate(false)}>I missed it</button>
            </div>
          )}
        </section>
      )}
    </Shell>
  );
}
