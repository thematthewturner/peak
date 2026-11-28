"use client";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import Shell from "@/components/Shell";
import Topo from "@/components/Topo";
import { capitalize, daysToSat, DOMAIN, greeting } from "@/lib/format";
import { useSession } from "@/lib/me";
import type { Preview, SkillMap, Stats } from "@/lib/types";

// One focused card that answers "what should I work on today?", says why in one sentence, and starts.
// The set behind it is mostly that skill, mixed with others (the score guide's interleaving); "Just this
// skill" under Change session makes it pure.
const LENGTHS = [15, 25, 45, 60];

function phase(days: number, hasBluebook: boolean): { name: string; line: string } {
  const weeks = Math.ceil(days / 7);
  if (!hasBluebook) return { name: "Diagnose", line: "Take Bluebook practice test 1 under real conditions. It shows where the points are." };
  if (weeks > 12) return { name: "Build", line: "Long runway: fix priority skills, mostly easy and medium questions, mixed sets." };
  if (weeks > 8) return { name: "Build", line: "Fix priority skills. Worked examples for new math, rules from memory." };
  if (weeks > 4) return { name: "Integrate", line: "Bluebook test every two weeks with a full review. Practice at test pace." };
  if (weeks > 1) return { name: "Simulate", line: "Bluebook at the real start time. Module 1 accuracy. Lock in sleep." };
  return { name: "Taper", line: "No new material. Light mixed sets and your sure-but-wrong log." };
}

export default function Today() {
  const { api, me } = useSession();
  const router = useRouter();
  const [minutes, setMinutes] = useState(45);
  const [section, setSection] = useState<string | null>(null);
  const [only, setOnly] = useState(false);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [active, setActive] = useState<{ id: string; left: number; total: number } | null>(null);
  const [skills, setSkills] = useState<SkillMap>({});
  const [stats, setStats] = useState<Stats | null>(null);
  const [change, setChange] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!me) return;
    api<SkillMap>("/skills").then(setSkills).catch(() => {});
    api<Stats>("/stats").then(setStats).catch(() => {});
    api<{ id: string; left: number; total: number } | null>("/sessions/active").then(setActive).catch(() => {});
  }, [api, me]);
  useEffect(() => {
    if (!me) return;
    const q = new URLSearchParams({ minutes: String(minutes) });
    if (section) q.set("section", section);
    if (only && preview?.focus_skill) q.set("only_skill", preview.focus_skill);
    api<Preview>(`/sessions/preview?${q}`).then(setPreview).catch((e) => setError(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, me, minutes, section, only]);

  const start = useCallback(() => {
    if (active) { router.push(`/session/?id=${active.id}`); return; }
    if (!preview) return;
    const q = new URLSearchParams({ minutes: String(minutes) });
    if (section) q.set("section", section);
    if (only && preview.focus_skill) q.set("only_skill", preview.focus_skill);
    router.push(`/session/?${q}`);
  }, [active, preview, minutes, section, only, router]);
  const onKey = useCallback((e: KeyboardEvent) => { if (e.key === "Enter") { e.preventDefault(); start(); } }, [start]);

  const days = daysToSat();
  const focus = preview?.focus_skill ? skills[preview.focus_skill] : undefined;
  const ph = phase(days, (stats?.latest_total ?? null) !== null);
  const count = (k: string) => preview?.blocks.find((b) => b.key === k)?.count ?? 0;
  const parts = [
    count("warmup") && `${count("warmup")} from your log`,
    count("learn") && "worked examples first",
    count("mixed") && `${count("mixed")} ${only ? "on this skill" : "mixed"}`,
    count("cards") && "rule cards",
  ].filter(Boolean);

  return (
    <Shell me={me} api={api} onKey={onKey}>
      <Topo />
      <div className="view today">
        <div className="hello">
          <p className="sub">{days} days to June 5 · {new Date().toLocaleDateString("en-US", { weekday: "long" })}</p>
          <h1 className="title">{greeting()}{me ? `, ${capitalize(me.username)}` : ""}</h1>
        </div>

        {active ? (
          <section className="focus-card">
            <span className="eyebrow">Pick up where you left off</span>
            <h2>{active.left} of {active.total} questions left</h2>
            <p className="why">Your answers so far are saved. Finish the set, then Peak plans the next one.</p>
            <div className="row"><button className="go" onClick={start}>Resume</button><button className="ghost" onClick={() => setActive(null)}>Start a new session instead</button></div>
          </section>
        ) : (
          <section className="focus-card" aria-live="polite">
            <span className="eyebrow">{preview?.throttled ? "School test soon" : "Today's focus"}</span>
            <h2>{preview?.throttled ? "Five minutes of rule cards" : focus ? `${focus.name}` : preview ? "Mixed practice" : " "}</h2>
            {focus && !preview?.throttled && <span className="domain">{DOMAIN[focus.domain]}</span>}
            <p className="why">{preview?.throttled ? "A school test is within three days, so today is light. Nothing due is lost." : preview?.focus_reason || " "}</p>
            <p className="meta">{preview ? `About ${preview.minutes} min · ${parts.join(" · ")}` : " "}</p>
            <div className="row">
              <button className="go" onClick={start} disabled={!preview}>Start practice</button>
              <button className="ghost" onClick={() => setChange((c) => !c)} aria-expanded={change}>Change session</button>
            </div>
            {change && (
              <div className="change">
                <div className="seg" role="group" aria-label="Length">{LENGTHS.map((m) => <button key={m} aria-pressed={minutes === m} onClick={() => setMinutes(m)}>{m} min</button>)}</div>
                <div className="seg" role="group" aria-label="Section">
                  {[[null, "Peak picks"], ["math", "Math"], ["rw", "Reading & Writing"]].map(([k, l]) => <button key={l} aria-pressed={section === k} onClick={() => { setSection(k); setOnly(false); }}>{l}</button>)}
                </div>
                <label className="check"><input id="only-skill" type="checkbox" checked={only} onChange={(e) => setOnly(e.target.checked)} />Just this skill, no mixing</label>
                {only && <p className="hint">Mixing types is the stronger method (score guide 4.2, grade A). Use this when a skill is brand new.</p>}
              </div>
            )}
            {error && <p className="err" role="alert">{error}</p>}
          </section>
        )}

        <div className="context">
          <div className="ctx">
            <span className="eyebrow">This week</span>
            <div className="dots" aria-label={`${stats?.week_sessions ?? 0} of ${stats?.week_target ?? 4} sessions this week`}>
              {Array.from({ length: stats?.week_target ?? 4 }, (_, i) => <i key={i} className={i < (stats?.week_sessions ?? 0) ? "on" : ""} />)}
            </div>
            <span className="hint">{stats?.week_sessions ?? 0} of {stats?.week_target ?? 4} sessions. Short and often beats one long cram.</span>
          </div>
          <div className="ctx">
            <span className="eyebrow">Phase · {ph.name}</span>
            <span className="hint">{ph.line}</span>
            {ph.name === "Diagnose" && <a className="hint" href="https://bluebook.collegeboard.org/students/download-bluebook" target="_blank" rel="noreferrer">Get Bluebook</a>}
          </div>
        </div>
      </div>
    </Shell>
  );
}
