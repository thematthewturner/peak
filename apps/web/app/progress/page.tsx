"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { useToast } from "@/components/Toast";
import { DOMAIN, SAT_DAY, shortDate } from "@/lib/format";
import { useSession } from "@/lib/me";
import type { AttemptRow, Series, SkillMap, Stats, Ticket } from "@/lib/types";

// Only clean Bluebook results (unseen form, one sitting, no help) are drawn as the trend.
// PSAT and official SAT scores sit on the same line as reference points; everything else is listed apart.
type Pt = { d: Date; v: number; kind: string };

function Chart({ points }: { points: Pt[] }) {
  const W = 640, H = 260, L = 46, R = 64, T = 22, B = 30;
  const first = points[0]?.d ?? new Date(2026, 9, 1);
  const x0 = new Date(first.getFullYear(), first.getMonth() - 1, 1).getTime();
  const x1 = Math.max(SAT_DAY.getTime() + 15 * 864e5, (points.at(-1)?.d.getTime() ?? 0) + 30 * 864e5);
  const lo = Math.min(1000, ...points.map((p) => p.v - 50)), hi = 1450;
  const X = (d: Date) => L + ((d.getTime() - x0) / (x1 - x0)) * (W - L - R);
  const Y = (v: number) => T + ((hi - v) / (hi - lo)) * (H - T - B);
  const ticks = [] as number[];
  for (let v = Math.ceil(lo / 100) * 100; v <= 1400; v += 100) ticks.push(v);
  const months: Date[] = [];
  for (let d = new Date(x0); d.getTime() <= x1; d = new Date(d.getFullYear(), d.getMonth() + 3, 1)) months.push(d);
  const line = points.map((p) => `${X(p.d).toFixed(1)},${Y(p.v).toFixed(1)}`);
  const last = points.at(-1);
  const sat = X(SAT_DAY);
  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Scores over time against the 1400 target${last ? `; latest ${last.v}` : ""}`}>
      {ticks.map((v) => (
        <g key={v}><line className="grid" x1={L} x2={W - R} y1={Y(v)} y2={Y(v)} /><text className="axis" x={L - 8} y={Y(v) + 4} textAnchor="end">{v}</text></g>
      ))}
      {months.map((m) => <text key={m.getTime()} className="axis" x={X(m)} y={H - 8} textAnchor="middle">{`${m.toLocaleDateString("en-US", { month: "short" })} ’${String(m.getFullYear()).slice(2)}`}</text>)}
      <line className="target" x1={L} x2={W - R} y1={Y(1400)} y2={Y(1400)} />
      <text className="target-t" x={W - R + 6} y={Y(1400) + 4}>1400</text>
      <line className="sat" x1={sat} x2={sat} y1={T} y2={H - B} />
      <text className="sat-t" x={sat - 4} y={T + 10} textAnchor="end">SAT · Jun 5</text>
      {points.length > 1 && <path className="area" d={`M${line.join(" L")} L${X(last!.d).toFixed(1)},${Y(lo)} L${X(points[0].d).toFixed(1)},${Y(lo)} Z`} />}
      {points.length > 1 && <polyline className="line" points={line.join(" ")} />}
      {points.map((p) => <circle key={p.d.getTime() + p.kind} className={`pt ${p.kind === "psat" ? "psat" : ""}`} cx={X(p.d)} cy={Y(p.v)} r={4.5} />)}
      {last && <text className="val" x={X(last.d) + 8} y={Y(last.v) - 8}>{last.v}</text>}
    </svg>
  );
}

export default function Progress() {
  const { api, me } = useSession();
  const { toast, node } = useToast();
  const [series, setSeries] = useState<Series | null>(null);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [attempts, setAttempts] = useState<AttemptRow[]>([]);
  const [form, setForm] = useState({ source: "psat", taken_on: "2026-10-15", rw: "620", math: "500", clean: false, recognized: false });
  const [stats, setStats] = useState<Stats | null>(null);
  const [skills, setSkills] = useState<SkillMap>({});
  const [tab, setTab] = useState<"math" | "rw">("math");
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api<Series>("/benchmarks").then(setSeries).catch(() => {});
    api<Ticket[]>("/tickets").then(setTickets).catch(() => {});
    api<AttemptRow[]>("/attempts?limit=50").then(setAttempts).catch(() => {});
    api<Stats>("/stats").then(setStats).catch(() => {});
    api<SkillMap>("/skills").then(setSkills).catch(() => {});
  }, [api]);
  useEffect(() => { if (me) load(); }, [me, load]);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    const clean = form.source === "bluebook" && form.clean;
    try {
      await api("/benchmarks", "POST", {
        source: form.source, taken_on: form.taken_on, rw_score: Number(form.rw) || null, math_score: Number(form.math) || null,
        unseen: clean, single_sitting: clean, uninterrupted: clean, unaided: clean, recognized: form.recognized,
      });
      toast(form.source === "bluebook" && (!clean || form.recognized) ? "Saved, kept apart from the clean trend." : "Saved.");
      setForm((f) => ({ ...f, source: "bluebook", rw: "", math: "", clean: true, recognized: false, taken_on: new Date().toISOString().slice(0, 10) }));
      load();
    } catch (err) { setError(err instanceof Error ? err.message : "That didn't save."); }
  }

  const pts: Pt[] = [];
  for (const kind of ["psat", "official_sat", "bluebook_clean"]) {
    for (const r of series?.[kind] ?? []) if (r.total) pts.push({ d: new Date(r.taken_on + "T00:00:00"), v: r.total, kind });
  }
  pts.sort((a, b) => a.d.getTime() - b.d.getTime());
  const latest = pts.at(-1);
  const proven = tickets.filter((t) => t.state === "CONFIRMED" || t.state === "MAINTAIN").length;
  const answered = attempts.filter((a) => a.correct !== null);
  const acc = answered.length ? Math.round((100 * answered.filter((a) => a.correct).length) / answered.length) : null;
  const exposed = series?.bluebook_exposed ?? [];
  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.type === "checkbox" ? (e.target as HTMLInputElement).checked : e.target.value }));

  return (
    <Shell me={me} api={api}>
      <div className="view">
        <div>
          <h1 className="title">Progress</h1>
          <p className="sub">Clean Bluebook results are the trend that counts: an unseen form, one sitting, no help. Use the median of your last two or three, not the best.</p>
        </div>
        {pts.length > 0 ? <Chart points={pts} /> : <p className="banner">No scores yet. Start with your October PSAT below: 620 Reading and Writing, 500 Math. Fix the date if you know the exact day.</p>}
        <div className="stats">
          <div className="stat"><b>{latest ? Math.max(0, 1400 - latest.v) : "–"}</b><span>points to the 1400 line</span></div>
          <div className="stat"><b>{proven}</b><span>fixes proven on fresh questions</span></div>
          <div className="stat"><b>{stats && stats.calibration.sure ? `${Math.round((100 * stats.calibration.sure_right) / stats.calibration.sure)}%` : acc === null ? "–" : `${acc}%`}</b><span>{stats && stats.calibration.sure ? `right when you're sure (${stats.calibration.sure_wrong} sure-but-wrong caught)` : `right, last ${answered.length || 50} answers`}</span></div>
        </div>
        <div className="panel">
          <div className="row spread">
            <b>Your skills</b>
            <div className="seg" role="group" aria-label="Section">
              <button aria-pressed={tab === "math"} onClick={() => setTab("math")}>Math</button>
              <button aria-pressed={tab === "rw"} onClick={() => setTab("rw")}>Reading &amp; Writing</button>
            </div>
          </div>
          <p className="hint">Practice counts: first tries on your own. These are drills, not an SAT score. Only Bluebook tells you that.</p>
          <table className="scores skills">
            <thead><tr><th>Skill</th><th>On your own</th><th>Last practiced</th><th>Where it stands</th></tr></thead>
            <tbody>
              {Object.entries(skills).filter(([, v]) => v.section === tab).sort((a, b) => (a[1].domain + a[1].name).localeCompare(b[1].domain + b[1].name)).map(([id, v]) => {
                const st = stats?.skills[id];
                const r = st?.recent_accuracy ?? null;
                const status = !st || st.attempts < 5 ? ["Still gathering evidence", ""] : (r ?? 0) >= 0.8 ? ["Solid", "ok"] : (r ?? 0) >= 0.6 ? ["Getting there", ""] : ["Priority", "warn"];
                return (
                  <tr key={id}>
                    <td><Link href={`/practice/?skill=${encodeURIComponent(id)}`}>{v.name}</Link><span className="hint"> · {DOMAIN[v.domain]}</span></td>
                    <td>{st ? `${st.correct} of ${st.attempts}` : "–"}</td>
                    <td>{st?.last ? shortDate(st.last) : "–"}</td>
                    <td><span className={`chip ${status[1]}`}>{status[0]}</span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <form className="panel" onSubmit={add}>
          <b>Log a score</b>
          <div className="form-grid">
            <label className="field">Test
              <select id="bm-source" value={form.source} onChange={set("source")}>
                <option value="psat">PSAT</option><option value="bluebook">Bluebook practice test</option><option value="official_sat">Official SAT</option>
              </select>
            </label>
            <label className="field">Date<input id="bm-date" type="date" value={form.taken_on} onChange={set("taken_on")} /></label>
            <label className="field">Reading and Writing<input id="bm-rw" inputMode="numeric" value={form.rw} onChange={set("rw")} placeholder="200–800" /></label>
            <label className="field">Math<input id="bm-math" inputMode="numeric" value={form.math} onChange={set("math")} placeholder="200–800" /></label>
          </div>
          {form.source === "bluebook" && (
            <>
              <label className="check"><input id="bm-clean" type="checkbox" checked={form.clean} onChange={set("clean")} />A form I&apos;d never seen, taken in one sitting, without help</label>
              <label className="check"><input id="bm-recognized" type="checkbox" checked={form.recognized} onChange={set("recognized")} />I recognized some questions from practice</label>
              <p className="hint">Peak&apos;s question bank may overlap with Bluebook forms; that hasn&apos;t been checked yet. A recognized question makes the score look better than it is, so it stays out of the trend.</p>
            </>
          )}
          {error && <p className="err" role="alert">{error}</p>}
          <button className="go" disabled={!form.rw || !form.math}>Save score</button>
        </form>
        {exposed.length > 0 && (
          <div className="panel">
            <b>Kept apart from the trend</b>
            <table className="scores"><thead><tr><th>Date</th><th>R&amp;W</th><th>Math</th><th>Total</th></tr></thead>
              <tbody>{exposed.map((r) => <tr key={r.id}><td>{r.taken_on}</td><td>{r.rw ?? "–"}</td><td>{r.math ?? "–"}</td><td>{r.total ?? "–"}</td></tr>)}</tbody>
            </table>
          </div>
        )}
      </div>
      {node}
    </Shell>
  );
}
