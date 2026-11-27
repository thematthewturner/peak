"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { Api } from "@/lib/api";
import type { Me } from "@/lib/types";

const LINKS = [
  ["/today", "Today"],
  ["/practice", "Practice"],
  ["/tickets", "Fixes"],
  ["/cards", "Cards"],
  ["/progress", "Progress"],
];

export default function Shell({ me, api, children }: { me: Me | null; api: Api; children: React.ReactNode }) {
  const path = usePathname();
  async function logout() {
    await api("/logout", "POST").catch(() => {});
    location.replace("/");
  }
  return (
    <main className="shell">
      <header className="nav">
        <nav aria-label="Main">
          {LINKS.map(([href, label]) => (
            <Link key={href} href={href} aria-current={path === href ? "page" : undefined}>
              {label}
            </Link>
          ))}
        </nav>
        {me && (
          <button className="btn ghost" onClick={logout}>
            Sign out
          </button>
        )}
      </header>
      {children}
    </main>
  );
}
