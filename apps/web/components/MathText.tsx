"use client";
import { useMemo } from "react";
import { renderMath } from "@/lib/math";

/** Text with math typeset by KaTeX ($$display$$, $inline$, `code`); everything else is escaped. */
export default function MathText({ text, className = "" }: { text: string; className?: string }) {
  const html = useMemo(() => renderMath(text), [text]);
  return <span className={`math-text ${className}`} dangerouslySetInnerHTML={{ __html: html }} />;
}
