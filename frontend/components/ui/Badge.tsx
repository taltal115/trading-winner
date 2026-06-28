import type { ReactNode } from "react";

type Tone = "neutral" | "positive" | "negative" | "warning" | "info" | "muted";

const toneClasses: Record<Tone, string> = {
  neutral: "bg-zinc-800 text-zinc-300 border-zinc-700",
  positive: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  negative: "bg-rose-500/10 text-rose-400 border-rose-500/30",
  warning: "bg-amber-500/10 text-amber-400 border-amber-500/30",
  info: "bg-sky-500/10 text-sky-400 border-sky-500/30",
  muted: "bg-zinc-800/50 text-zinc-500 border-zinc-800",
};

export function Badge({
  children,
  tone = "neutral",
  className = "",
}: {
  children: ReactNode;
  tone?: Tone;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium ${toneClasses[tone]} ${className}`}
    >
      {children}
    </span>
  );
}

export function Dot({ tone = "neutral" }: { tone?: Tone }) {
  const colors: Record<Tone, string> = {
    neutral: "bg-zinc-400",
    positive: "bg-emerald-400",
    negative: "bg-rose-400",
    warning: "bg-amber-400",
    info: "bg-sky-400",
    muted: "bg-zinc-600",
  };
  return (
    <span className={`inline-block h-2 w-2 rounded-full ${colors[tone]}`} />
  );
}
