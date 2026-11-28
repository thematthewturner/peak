"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { Api } from "@/lib/api";
import { daysToSat } from "@/lib/format";
import type { Me, Ticket } from "@/lib/types";

const ICON: Record<string, React.ReactNode> = {
  today: <path d="M2 15h16M5 15a5 5 0 0 1 10 0M10 4v2M3.8 7.8l1.4 1.4M16.2 7.8l-1.4 1.4" />,
  practice: <path d="M3 16.5 13.5 6l1.9 1.9L4.9 18.4H3v-1.9ZM12 4.5l1.6-1.6a1.3 1.3 0 0 1 1.9 0l1.6 1.6a1.3 1.3 0 0 1 0 1.9L15.5 8" />,
  fixes: <path d="M2.5 17 8 7l3 5 2.5-3.5L17.5 17h-15ZM8 7V3l3 1.3L8 5.6" />,
  cards: <><rect x="3" y="5.5" width="11" height="11" rx="2" /><path d="M6.5 3.5h8a2 2 0 0 1 2 2v8" /></>,
  progress: <path d="M2.5 16.5h15M3.5 13l4-4 3 2.5 6-6.5" />,
};
const PLACES = [["today", "Today"], ["practice", "Practice"], ["fixes", "Fixes"], ["cards", "Cards"], ["progress", "Progress"]] as const;

export default function Shell({ me, api, children, onKey }: {
  me: Me | null; api: Api; children: React.ReactNode; onKey?: (e: KeyboardEvent) => void;
}) {
  const path = (usePathname() || "/").replace(/\/$/, "");
  const router = useRouter();
  const [counts, setCounts] = useState<{ fixes?: number; cards?: number }>({});

  useEffect(() => {
    if (!me) return;
    api<Ticket[]>("/tickets").then((t) => setCounts((c) => ({ ...c, fixes: t.filter((x) => !["CONFIRMED", "MAINTAIN"].includes(x.state)).length }))).catch(() => {});
    api<unknown[]>("/cards/due").then((c) => setCounts((x) => ({ ...x, cards: c.length }))).catch(() => {});
  }, [api, me, path]);

  // Keep the newest page handler in a ref, updated during commit (layout effect), so a key pressed right
  // after a state change never reaches a stale handler. The listener itself is registered once.
  const keyRef = useRef(onKey);
  useLayoutEffect(() => { keyRef.current = onKey; });
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.metaKey && /^[1-5]$/.test(e.key)) {
        e.preventDefault();
        router.push(`/${PLACES[Number(e.key) - 1][0]}/`);
        return;
      }
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === "INPUT" || t.tagName === "SELECT" || t.tagName === "TEXTAREA")) {
        if (e.key !== "Enter") return;
      }
      keyRef.current?.(e);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [router]);

  async function signOut() {
    await api("/logout", "POST").catch(() => {});
    location.replace("/");
  }

  const days = daysToSat();
  return (
    <div className="app">
      <aside className="side">
        <div className="brand"><svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M2 16.5 8 6l3.5 6 2-3 4.5 7.5H2Z" /></svg>Peak</div>
        <nav className="nav" aria-label="Peak">
          {PLACES.map(([key, label]) => (
            <Link key={key} href={`/${key}/`} aria-current={path === `/${key}` ? "page" : undefined}>
              <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6">{ICON[key]}</svg>
              {label}
              {key === "fixes" && counts.fixes ? <span className="count">{counts.fixes}</span> : null}
              {key === "cards" && counts.cards ? <span className="count">{counts.cards}</span> : null}
            </Link>
          ))}
        </nav>
        <div className="side-foot">
          <span>June 5 SAT</span>
          <b>{days} days</b>
          {me?.role === "parent" && <button onClick={signOut}>Sign out</button>}
        </div>
      </aside>
      <main className="main" id="main">{children}</main>
    </div>
  );
}
