"use client";
import { useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { CAUSE, DOMAIN, shortDate } from "@/lib/format";
import { useSession } from "@/lib/me";
import type { MicroSkill, SkillMap, Taxonomy, Ticket } from "@/lib/types";

// Each miss climbs five rungs; only a fresh question a week after the repair counts as proof.
const RUNGS = ["Missed", "Repaired", "Retry", "Proof", "Proven"];
const AT: Record<string, number> = { OPEN: 0, REOPENED: 0, REPAIRING: 1, RETRY_DUE: 2, TRANSFER_DUE: 3, CONFIRMED: 4, MAINTAIN: 4 };

function nextLine(t: Ticket): string {
  if (t.state === "CONFIRMED" || t.state === "MAINTAIN") return "Proven on a fresh question";
  if (t.state === "RETRY_DUE") return t.next_due ? `Retry ${shortDate(t.next_due)}` : "Retry due";
  if (t.state === "TRANSFER_DUE") return t.next_due ? `Proof ${shortDate(t.next_due)} · unlabeled, mixed set` : "Proof due";
  if (t.state === "REOPENED") return "Reopened";
  return "Needs a repair";
}

export default function Fixes() {
  const { api, me } = useSession();
  const [rows, setRows] = useState<Ticket[] | null>(null);
  const [micro, setMicro] = useState<Record<string, MicroSkill>>({});
  const [skills, setSkills] = useState<SkillMap>({});

  useEffect(() => {
    if (!me) return;
    api<Ticket[]>("/tickets").then(setRows).catch(() => setRows([]));
    api<Taxonomy>("/taxonomy").then((t) => setMicro(Object.fromEntries(t.micro_skills.map((m) => [m.key, m])))).catch(() => {});
    api<SkillMap>("/skills").then(setSkills).catch(() => {});
  }, [api, me]);

  const open = rows?.filter((t) => AT[t.state] < 4) ?? [];
  const proven = rows?.filter((t) => AT[t.state] === 4) ?? [];
  const list = [...open, ...proven];
  return (
    <Shell me={me} api={api}>
      <div className="view">
        <div>
          <h1 className="title">Fixes</h1>
          <p className="sub">Each miss climbs five rungs. Only a fresh question a week later counts as proof.</p>
        </div>
        {rows && rows.length === 0 && <p className="sub">No fixes yet. When you miss a question in Practice and name what happened, it shows up here.</p>}
        <div>
          {list.map((t) => {
            const at = AT[t.state] ?? 0;
            const name = t.micro_skill ? micro[t.micro_skill]?.label ?? t.micro_skill : CAUSE[t.cause] ?? t.cause;
            const skill = skills[t.skill_id];
            return (
              <div className="fix" key={t.id}>
                <div className="row spread">
                  <span><b style={{ fontSize: 15 }}>{name}</b>{skill && <span className="hint"> · {DOMAIN[skill.domain] ?? ""}, {skill.name}</span>}</span>
                  <span className="hint">{nextLine(t)}</span>
                </div>
                <div className="ladder" aria-label={`Rung ${at + 1} of 5: ${RUNGS[at]}`}>
                  {RUNGS.map((r, i) => {
                    const cls = at === 4 ? (i === 4 ? "summit" : "done") : i < at ? "done" : i === at ? "now" : "";
                    return <span key={r} className={`rung ${cls}`}><i />{r}</span>;
                  })}
                </div>
                {t.reopen_reason && <span className="hint err">Reopened: {t.reopen_reason}</span>}
                {t.cue && <span className="cue">{t.cue}</span>}
              </div>
            );
          })}
        </div>
      </div>
    </Shell>
  );
}
