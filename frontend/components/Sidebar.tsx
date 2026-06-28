"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS: { href: string; label: string; description: string }[] = [
  { href: "/", label: "Dashboard", description: "System & status" },
  { href: "/signals", label: "Signals", description: "Ranked opportunities" },
  { href: "/portfolio", label: "Portfolio", description: "Equity & positions" },
  { href: "/trades", label: "Trades", description: "Execution history" },
  { href: "/backtests", label: "Backtests", description: "Strategy metrics" },
  { href: "/ai", label: "AI Analyses", description: "Reasoning logs" },
];

function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex shrink-0 flex-col border-b border-zinc-800 bg-zinc-950/60 md:h-screen md:w-64 md:border-b-0 md:border-r">
      <div className="flex items-center gap-2 px-5 py-5">
        <span className="inline-flex h-8 w-8 items-center justify-center rounded-md bg-emerald-500/15 text-sm font-bold text-emerald-400">
          AI
        </span>
        <div className="leading-tight">
          <div className="text-sm font-semibold text-zinc-100">
            Trading Intel
          </div>
          <div className="text-xs text-zinc-500">Read-only dashboard</div>
        </div>
      </div>

      <nav className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-col md:gap-0.5 md:overflow-visible md:pb-0">
        {NAV_ITEMS.map((item) => {
          const active = isActive(pathname, item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`group flex shrink-0 flex-col rounded-lg px-3 py-2 transition-colors md:shrink ${
                active
                  ? "bg-zinc-800/80 text-zinc-50"
                  : "text-zinc-400 hover:bg-zinc-800/40 hover:text-zinc-200"
              }`}
            >
              <span className="text-sm font-medium">{item.label}</span>
              <span className="hidden text-xs text-zinc-500 md:block">
                {item.description}
              </span>
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto hidden px-5 py-4 md:block">
        <p className="text-[11px] leading-relaxed text-zinc-600">
          The UI does not decide trades — it explains them. All actions are
          read-only.
        </p>
      </div>
    </aside>
  );
}
