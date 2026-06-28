import Link from "next/link";
import { api } from "@/lib/api";
import { formatNumber, formatPercent } from "@/lib/format";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { StatCard } from "@/components/ui/StatCard";
import { ApiErrorState } from "@/components/ui/States";
import {
  CatalystDirectionBadge,
  SentimentBadge,
} from "@/components/DomainBadges";

export const dynamic = "force-dynamic";

export default async function AiAnalysisDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const result = await api.getAiAnalysis(id);

  if (!result.ok) {
    return (
      <div>
        <BackLink />
        <PageHeader title="AI Analysis" description={id} />
        <ApiErrorState title="Analysis unavailable" message={result.error} />
      </div>
    );
  }

  const ai = result.data;

  return (
    <div>
      <BackLink />
      <PageHeader
        title={`${ai.ticker} — AI Analysis`}
        description={ai.id}
        action={
          <div className="flex flex-wrap gap-2">
            <Badge tone="muted">{ai.catalyst_type}</Badge>
            <CatalystDirectionBadge direction={ai.catalyst_direction} />
            <SentimentBadge sentiment={ai.sentiment} />
          </div>
        }
      />

      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Confidence" value={formatPercent(ai.confidence)} />
        <StatCard label="AI Bias" value={formatNumber(ai.ai_bias, 2)} />
        <StatCard
          label="Confidence Adj."
          value={formatNumber(ai.confidence_adjustment, 2)}
        />
        <StatCard
          label="Related ID"
          value={<span className="text-base">{ai.related_id}</span>}
        />
      </div>

      <Card className="mb-6">
        <CardHeader title="Summary" />
        <CardBody>
          <p className="text-sm leading-relaxed text-zinc-300">{ai.summary}</p>
        </CardBody>
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Key Insights" />
          <CardBody>
            {ai.key_insights.length === 0 ? (
              <p className="text-sm text-zinc-500">No insights recorded.</p>
            ) : (
              <ul className="space-y-2 text-sm text-zinc-300">
                {ai.key_insights.map((insight, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="text-emerald-500">•</span>
                    <span>{insight}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Risk Factors" />
          <CardBody>
            {ai.risk_factors.length === 0 ? (
              <p className="text-sm text-zinc-500">No risk factors recorded.</p>
            ) : (
              <ul className="space-y-2 text-sm text-zinc-300">
                {ai.risk_factors.map((risk, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="text-rose-500">•</span>
                    <span>{risk}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>
      </div>

      <Card className="mt-6">
        <CardHeader
          title="Provenance"
          subtitle="Versioning for reproducibility"
        />
        <CardBody>
          <dl className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <Meta label="Reasoning version" value={ai.reasoning_version} />
            <Meta label="Prompt version" value={ai.prompt_version} />
            <Meta label="Embedding version" value={ai.embedding_version} />
          </dl>
        </CardBody>
      </Card>
    </div>
  );
}

function BackLink() {
  return (
    <Link
      href="/ai"
      className="mb-4 inline-flex items-center gap-1 text-sm text-zinc-500 transition-colors hover:text-zinc-300"
    >
      ← Back to analyses
    </Link>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-zinc-500">{label}</dt>
      <dd className="mt-1 font-mono text-sm text-zinc-200">{value}</dd>
    </div>
  );
}
