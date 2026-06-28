import { api } from "@/lib/api";
import { formatNumber, formatPercent } from "@/lib/format";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { ApiErrorState, EmptyState } from "@/components/ui/States";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/Table";
import {
  CatalystDirectionBadge,
  DecisionBadge,
  SentimentBadge,
} from "@/components/DomainBadges";
import type { AiAnalysis } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function SignalsPage() {
  const [signalsResult, aiResult] = await Promise.all([
    api.getSignals(100),
    api.getAiAnalyses(),
  ]);

  if (!signalsResult.ok) {
    return (
      <div>
        <PageHeader title="Signals" description="Ranked trade opportunities." />
        <ApiErrorState message={signalsResult.error} />
      </div>
    );
  }

  // Best-effort AI enrichment; signals still render if the AI endpoint is down.
  const aiById = new Map<string, AiAnalysis>();
  if (aiResult.ok) {
    for (const analysis of aiResult.data) aiById.set(analysis.id, analysis);
  }

  const signals = [...signalsResult.data].sort((a, b) => b.score - a.score);

  return (
    <div>
      <PageHeader
        title="Signals"
        description="Ranked opportunities sorted by score. AI enrichment shown where available."
        action={<Badge tone="info">{signals.length} signals</Badge>}
      />

      <Card>
        {signals.length === 0 ? (
          <EmptyState message="No signals generated yet." />
        ) : (
          <Table>
            <THead>
              <TR>
                <TH>Ticker</TH>
                <TH align="right">Score</TH>
                <TH>Decision</TH>
                <TH align="right">Exp. Return</TH>
                <TH align="right">Risk</TH>
                <TH>AI Bias</TH>
                <TH>Catalyst</TH>
                <TH>Sentiment</TH>
                <TH>AI Summary</TH>
              </TR>
            </THead>
            <TBody>
              {signals.map((signal) => {
                const ai = signal.ai_analysis_id
                  ? aiById.get(signal.ai_analysis_id)
                  : undefined;
                return (
                  <TR key={signal.id}>
                    <TD className="font-semibold text-zinc-100">
                      {signal.ticker}
                    </TD>
                    <TD align="right" className="tabular-nums text-zinc-100">
                      {formatNumber(signal.score, 1)}
                    </TD>
                    <TD>
                      <DecisionBadge decision={signal.decision} />
                    </TD>
                    <TD align="right" className="tabular-nums">
                      {formatPercent(signal.expected_return, { signed: true })}
                    </TD>
                    <TD align="right" className="tabular-nums text-zinc-400">
                      {formatNumber(signal.risk_score, 1)}
                    </TD>
                    <TD>
                      {ai ? (
                        <span className="tabular-nums text-zinc-300">
                          {formatNumber(ai.ai_bias, 2)}
                        </span>
                      ) : (
                        <span className="text-zinc-600">—</span>
                      )}
                    </TD>
                    <TD>
                      {ai ? (
                        <CatalystDirectionBadge
                          direction={ai.catalyst_direction}
                        />
                      ) : (
                        <span className="text-zinc-600">—</span>
                      )}
                    </TD>
                    <TD>
                      {ai ? (
                        <SentimentBadge sentiment={ai.sentiment} />
                      ) : (
                        <span className="text-zinc-600">—</span>
                      )}
                    </TD>
                    <TD className="max-w-xs">
                      {ai ? (
                        <span className="line-clamp-2 text-zinc-400">
                          {ai.summary}
                        </span>
                      ) : signal.ai_analysis_id ? (
                        <span className="text-zinc-600">
                          (analysis {signal.ai_analysis_id})
                        </span>
                      ) : (
                        <span className="text-zinc-600">quant-only</span>
                      )}
                    </TD>
                  </TR>
                );
              })}
            </TBody>
          </Table>
        )}
      </Card>

      {!aiResult.ok ? (
        <p className="mt-3 text-xs text-amber-500/80">
          AI enrichment unavailable ({aiResult.error}); showing quant signal
          data only.
        </p>
      ) : null}
    </div>
  );
}
