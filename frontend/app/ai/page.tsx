import Link from "next/link";
import { api } from "@/lib/api";
import { formatNumber, formatPercent } from "@/lib/format";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { ApiErrorState, EmptyState } from "@/components/ui/States";
import {
  CatalystDirectionBadge,
  SentimentBadge,
} from "@/components/DomainBadges";

export const dynamic = "force-dynamic";

export default async function AiAnalysesPage() {
  const analyses = await api.getAiAnalyses();

  if (!analyses.ok) {
    return (
      <div>
        <PageHeader title="AI Analyses" description="AI reasoning logs." />
        <ApiErrorState message={analyses.error} />
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="AI Analyses"
        description="LLM enrichment logs. Advisory only — never an execution authority."
        action={<Badge tone="info">{analyses.data.length} analyses</Badge>}
      />

      {analyses.data.length === 0 ? (
        <Card>
          <EmptyState message="No AI analyses recorded yet." />
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {analyses.data.map((ai) => (
            <Link key={ai.id} href={`/ai/${encodeURIComponent(ai.id)}`}>
              <Card className="h-full transition-colors hover:border-zinc-700 hover:bg-zinc-900">
                <div className="flex flex-col gap-3 px-5 py-4">
                  <div className="flex items-center justify-between">
                    <span className="text-base font-semibold text-zinc-100">
                      {ai.ticker}
                    </span>
                    <Badge tone="muted">{ai.catalyst_type}</Badge>
                  </div>
                  <p className="line-clamp-3 text-sm text-zinc-400">
                    {ai.summary}
                  </p>
                  <div className="flex flex-wrap items-center gap-2">
                    <CatalystDirectionBadge direction={ai.catalyst_direction} />
                    <SentimentBadge sentiment={ai.sentiment} />
                  </div>
                  <div className="flex items-center justify-between border-t border-zinc-800 pt-3 text-xs text-zinc-500">
                    <span>
                      Confidence{" "}
                      <span className="text-zinc-300">
                        {formatPercent(ai.confidence)}
                      </span>
                    </span>
                    <span>
                      Bias{" "}
                      <span className="text-zinc-300">
                        {formatNumber(ai.ai_bias, 2)}
                      </span>
                    </span>
                  </div>
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
