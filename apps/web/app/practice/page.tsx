"use client";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import QuestionCard from "@/components/QuestionCard";
import Shell from "@/components/Shell";
import { tipFaded, tipFor } from "@/lib/coach";
import { DOMAIN } from "@/lib/format";
import { useSession } from "@/lib/me";
import { ApiError } from "@/lib/session";
import type { Item, SkillMap, Stats, Taxonomy } from "@/lib/types";

// Free practice on one skill (opened from Progress). Guided sessions live on Today.
function Practice() {
  const { api, me } = useSession();
  const skill = useSearchParams().get("skill");
  const [item, setItem] = useState<Item | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "empty" | "nobank">("loading");
  const [tax, setTax] = useState<Taxonomy | null>(null);
  const [skills, setSkills] = useState<SkillMap>({});
  const [stats, setStats] = useState<Stats | null>(null);
  const [count, setCount] = useState(0);
  const [error, setError] = useState("");
  const keyRef = useRef<((e: KeyboardEvent) => void) | null>(null);

  const load = useCallback(async () => {
    setState("loading"); setError("");
    const q = skill ? `?skill_id=${encodeURIComponent(skill)}&allow_seen=true` : "?allow_seen=true";
    try {
      setItem(await api<Item>(`/items/next${q}`)); setState("ready"); setCount((c) => c + 1);
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        const b = await api<{ ready: number }>("/bank").catch(() => null);
        setState(b && b.ready === 0 ? "nobank" : "empty");
      } else { setError(e instanceof Error ? e.message : "Couldn't load a question."); setState("empty"); }
    }
  }, [api, skill]);
  useEffect(() => { if (me) void load(); }, [me, load]);
  useEffect(() => {
    if (!me) return;
    api<Taxonomy>("/taxonomy").then(setTax).catch(() => {});
    api<SkillMap>("/skills").then(setSkills).catch(() => {});
    api<Stats>("/stats").then(setStats).catch(() => {});
  }, [api, me]);
  const onKey = useCallback((e: KeyboardEvent) => keyRef.current?.(e), []);

  const sk = item?.skill_id ? skills[item.skill_id] : skill ? skills[skill] : undefined;
  return (
    <Shell me={me} api={api} onKey={onKey}>
      <div className="view session">
        <div className="row spread">
          <h1 className="title" style={{ fontSize: 20 }}>{skill && sk ? sk.name : "Practice"}</h1>
          <span className="hint">{sk ? DOMAIN[sk.domain] : ""}{count ? ` · question ${count}` : ""}</span>
        </div>
        {error && <p className="err" role="alert">{error}</p>}
        {state === "nobank" && (
          <div className="banner"><b>No questions are loaded yet.</b> Load the question bank from Terminal, then come back:
            <pre className="cmd">cd ~/code/peak/services/backend{"\n"}uv run python -m peak.local import PATH/TO/collegeboard_qbank.jsonl</pre>
          </div>
        )}
        {state === "empty" && !error && <p className="banner">Nothing left to practice here right now.</p>}
        {state === "ready" && item && (
          <QuestionCard key={`${count}-${item.id}`} api={api} item={item} tax={tax} section={sk?.section}
            skillName={sk?.name} tip={tipFaded(stats?.skills[item.skill_id ?? ""]) ? null : tipFor(item.skill_id)}
            onDone={() => load()} onKeyRef={keyRef} />
        )}
      </div>
    </Shell>
  );
}

export default function Page() {
  return <Suspense><Practice /></Suspense>;
}
