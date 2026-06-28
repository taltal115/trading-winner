import { api } from "@/lib/api";
import {
  formatDate,
  formatNumber,
  formatPercent,
  pnlColor,
} from "@/lib/format";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { ApiErrorState, EmptyState } from "@/components/ui/States";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/Table";

export const dynamic = "force-dynamic";

export default async function BacktestsPage() {
  const backtests = await api.getBacktests();

  if (!backtests.ok) {
    return (
      <div>
        <PageHeader title="Backtests" description="Strategy performance." />
        <ApiErrorState message={backtests.error} />
      </div>
    );
  }

  const sorted = [...backtests.data].sort(
    (a, b) =>
      new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  );

  return (
    <div>
      <PageHeader
        title="Backtests"
        description="Historical strategy runs with Sharpe, win rate, drawdown, and total return."
        action={<Badge tone="info">{sorted.length} runs</Badge>}
      />

      <Card>
        {sorted.length === 0 ? (
          <EmptyState message="No backtests have been run yet." />
        ) : (
          <Table>
            <THead>
              <TR>
                <TH>Strategy</TH>
                <TH>Period</TH>
                <TH align="right">Tickers</TH>
                <TH align="right">Trades</TH>
                <TH align="right">Sharpe</TH>
                <TH align="right">Win Rate</TH>
                <TH align="right">Max Drawdown</TH>
                <TH align="right">Total Return</TH>
              </TR>
            </THead>
            <TBody>
              {sorted.map((b) => (
                <TR key={b.id}>
                  <TD className="font-medium text-zinc-100">{b.strategy}</TD>
                  <TD className="text-zinc-400">
                    {formatDate(b.start_date)} → {formatDate(b.end_date)}
                  </TD>
                  <TD align="right" className="tabular-nums text-zinc-400">
                    {b.tickers.length}
                  </TD>
                  <TD align="right" className="tabular-nums">
                    {b.trade_count}
                  </TD>
                  <TD
                    align="right"
                    className={`tabular-nums font-medium ${
                      b.metrics.sharpe >= 1.2
                        ? "text-emerald-400"
                        : "text-zinc-300"
                    }`}
                  >
                    {formatNumber(b.metrics.sharpe, 2)}
                  </TD>
                  <TD align="right" className="tabular-nums">
                    {formatPercent(b.metrics.win_rate)}
                  </TD>
                  <TD align="right" className="tabular-nums text-rose-300">
                    {formatPercent(b.metrics.max_drawdown)}
                  </TD>
                  <TD
                    align="right"
                    className={`tabular-nums font-medium ${pnlColor(b.metrics.total_return)}`}
                  >
                    {formatPercent(b.metrics.total_return, { signed: true })}
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        )}
      </Card>
    </div>
  );
}
