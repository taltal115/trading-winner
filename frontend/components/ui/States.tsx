import type { ReactNode } from "react";
import { Card } from "@/components/ui/Card";

/** Friendly message shown when the backend is unreachable or returns an error. */
export function ApiErrorState({
  title = "API unavailable",
  message,
}: {
  title?: string;
  message: string;
}) {
  return (
    <Card className="border-rose-500/30 bg-rose-500/5">
      <div className="flex flex-col items-start gap-2 px-5 py-6">
        <div className="flex items-center gap-2">
          <span className="inline-block h-2.5 w-2.5 rounded-full bg-rose-400" />
          <h3 className="text-sm font-semibold text-rose-300">{title}</h3>
        </div>
        <p className="text-sm text-zinc-400">{message}</p>
        <p className="text-xs text-zinc-600">
          Make sure the backend is running and reachable, then refresh.
        </p>
      </div>
    </Card>
  );
}

export function EmptyState({
  message = "No data yet.",
  children,
}: {
  message?: string;
  children?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-5 py-12 text-center">
      <p className="text-sm text-zinc-500">{message}</p>
      {children}
    </div>
  );
}

/** Skeleton placeholder for streamed/loading content. */
export function LoadingSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="space-y-3 px-5 py-4">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="h-9 animate-pulse rounded-md bg-zinc-800/60"
          style={{ animationDelay: `${i * 80}ms` }}
        />
      ))}
    </div>
  );
}
