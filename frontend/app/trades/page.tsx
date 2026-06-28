import { api } from "@/lib/api";
import {
  formatCurrency,
  formatDateTime,
  formatNumber,
  pnlColor,
} from "@/lib/format";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { ApiErrorState, EmptyState } from "@/components/ui/States";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/Table";
import { TradeStatusBadge } from "@/components/DomainBadges";

export const dynamic = "force-dynamic";

export default async function TradesPage() {
  const trades = await api.getTrades();

  if (!trades.ok) {
    return (
      <div>
        <PageHeader title="Trades" description="Execution history." />
        <ApiErrorState message={trades.error} />
      </div>
    );
  }

  const sorted = [...trades.data].sort(
    (a, b) =>
      new Date(b.entry_time).getTime() - new Date(a.entry_time).getTime(),
  );
  const open = sorted.filter((t) => t.status === "OPEN").length;

  return (
    <div>
      <PageHeader
        title="Trades"
        description="Trade history with entry/exit, status, and realized PnL."
        action={
          <div className="flex gap-2">
            <Badge tone="info">{open} open</Badge>
            <Badge tone="neutral">{sorted.length} total</Badge>
          </div>
        }
      />

      <Card>
        {sorted.length === 0 ? (
          <EmptyState message="No trades recorded yet." />
        ) : (
          <Table>
            <THead>
              <TR>
                <TH>Ticker</TH>
                <TH>Side</TH>
                <TH>Status</TH>
                <TH>Entry Time</TH>
                <TH align="right">Entry</TH>
                <TH>Exit Time</TH>
                <TH align="right">Exit</TH>
                <TH align="right">Qty</TH>
                <TH align="right">PnL</TH>
              </TR>
            </THead>
            <TBody>
              {sorted.map((t) => (
                <TR key={t.id}>
                  <TD className="font-semibold text-zinc-100">{t.ticker}</TD>
                  <TD>
                    <Badge tone={t.side === "LONG" ? "positive" : "negative"}>
                      {t.side}
                    </Badge>
                  </TD>
                  <TD>
                    <TradeStatusBadge status={t.status} />
                  </TD>
                  <TD className="text-zinc-400">
                    {formatDateTime(t.entry_time)}
                  </TD>
                  <TD align="right" className="tabular-nums">
                    {formatCurrency(t.entry_price)}
                  </TD>
                  <TD className="text-zinc-400">
                    {formatDateTime(t.exit_time)}
                  </TD>
                  <TD align="right" className="tabular-nums">
                    {t.exit_price === null ? "—" : formatCurrency(t.exit_price)}
                  </TD>
                  <TD align="right" className="tabular-nums">
                    {formatNumber(t.quantity, 0)}
                  </TD>
                  <TD
                    align="right"
                    className={`tabular-nums font-medium ${pnlColor(t.pnl)}`}
                  >
                    {t.pnl === null ? "—" : formatCurrency(t.pnl)}
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
