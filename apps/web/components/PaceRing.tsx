"use client";
import { useEffect, useState } from "react";

/** A quiet ring that fills to test pace (~71 s R&W, ~95 s Math). Past twice the pace it suggests moving on. */
export default function PaceRing({ start, target, running }: { start: number; target: number; running: boolean }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [running]);
  const secs = Math.max(0, Math.round((now - start) / 1000));
  const frac = Math.min(1, secs / target);
  const over = secs > target, long = secs > target * 2;
  const r = 15, c = 2 * Math.PI * r;
  return (
    <span className={`pace ${over ? "over" : ""}`} title={`Test pace is about ${target} seconds a question`}>
      <svg viewBox="0 0 36 36" aria-hidden="true">
        <circle cx="18" cy="18" r={r} className="track" />
        <circle cx="18" cy="18" r={r} className="fill" strokeDasharray={`${frac * c} ${c}`} transform="rotate(-90 18 18)" />
      </svg>
      <span className="secs">{secs < 60 ? `${secs}s` : `${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, "0")}`}</span>
      {long && <span className="nudge">On test day, flag this one and come back.</span>}
    </span>
  );
}
