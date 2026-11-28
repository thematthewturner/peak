"use client";
import type { Solved as SolvedItem } from "@/lib/types";

export function Html({ html, className = "" }: { html: string | null | undefined; className?: string }) {
  // Item HTML is sanitized to an allowlist when it is imported; this renders that safe subset.
  return html ? <div className={`html ${className}`} dangerouslySetInnerHTML={{ __html: html }} /> : null;
}

/** A worked example: the question with its answer marked and the official explanation. */
export default function Solved({ item, compact = false }: { item: SolvedItem; compact?: boolean }) {
  return (
    <div className={`solved ${compact ? "compact" : ""}`}>
      {item.passage && <Html html={item.passage} className="passage solo" />}
      <Html html={item.stem} className="stem" />
      {item.format === "mc" && item.choices ? (
        <div className="choices">
          {Object.entries(item.choices).map(([L, h]) => (
            <div key={L} className={`choice static ${item.key.includes(L) ? "right" : "dim"}`}><span className="L">{L}</span><Html html={h} /></div>
          ))}
        </div>
      ) : <p className="answer-line">Answer: <b>{item.key.join(" or ")}</b></p>}
      {item.rationale && (
        <div className="explain"><span className="kind">How it&apos;s solved</span><Html html={item.rationale} /></div>
      )}
    </div>
  );
}
