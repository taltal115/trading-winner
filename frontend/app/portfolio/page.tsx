import { api } from "@/lib/api";
import {
  formatCurrency,
  formatDateTime,
  formatNumber,
  pnlColor,
} from "@/lib/format";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { StatCard } from "@/components/ui/StatCard";
import { Badge } from "@/components/ui/Badge";
import { ApiErrorState, EmptyState } from "@/components/ui/States";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/Table";
import type { ReconciliationReport } from "@/lib/types";

export const dynamic = "force-dynamic";

function ReconciliationCard({ report }: { report: ReconciliationReport }) {
  return (
    <Card className={report.in_sync ? "" : "border-amber-500/30"}>
      <CardHeader
        title="Position Reconciliation"
        subtitle="Internal vs. broker truth (read-only detection)"
        action={
          <Badge tone={report.in_sync ? "positive" : "warning"}>
            {report.in_sync
              ? "IN SYNC"
              : `${report.discrepancies.length} DRIFT`}
          </Badge>
        }
      />
      <CardBody>
        {report.in_sync ? (
          <p className="text-sm text-zinc-500">
            {report.matched.length} position(s) matched. No drift detected.
          </p>
        ) : (
          <Table>
            <THead>
              <TR>
                <TH>Ticker</TH>
                <TH>Kind</TH>
                <TH align="right">Internal Qty</TH>
                <TH align="right">Broker Qty</TH>
              </TR>
            </THead>
            <TBody>
              {report.discrepancies.map((d) => (
                <TR key={d.ticker}>
                  <TD className="font-medium text-zinc-100">{d.ticker}</TD>
                  <TD>
                    <Badge tone="warning">{d.kind.replace(/_/g, " ")}</Badge>
                  </TD>
                  <TD align="right" className="tabular-nums">
                    {formatNumber(d.internal_quantity, 0)}
                  </TD>
                  <TD align="right" className="tabular-nums">
                    {formatNumber(d.broker_quantity, 0)}
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        )}
      </CardBody>
    </Card>
  );
}

export default async function PortfolioPage() {
  const [portfolio, positions, reconciliation] = await Promise.all([
    api.getPortfolio(),
    api.getPositions(),
    api.getReconciliation(),
  ]);

  return (
    <div>
      <PageHeader
        title="Portfolio & Positions"
        description="Account equity, cash, and open positions with live exit levels."
      />

      {portfolio.ok ? (
        <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
          <StatCard
            label="Equity"
            value={formatCurrency(portfolio.data.equity)}
          />
          <StatCard label="Cash" value={formatCurrency(portfolio.data.cash)} />
          <StatCard
            label="Exposure"
            value={formatCurrency(portfolio.data.exposure)}
          />
          <StatCard
            label="Open Positions"
            value={String(portfolio.data.open_positions)}
            hint={`Updated ${formatDateTime(portfolio.data.updated_at)}`}
          />
        </div>
      ) : (
        <div className="mb-6">
          <ApiErrorState
            title="Portfolio unavailable"
            message={portfolio.error}
          />
        </div>
      )}

      <Card className="mb-6">
        <CardHeader title="Open Positions" subtitle="GET /positions" />
        {!positions.ok ? (
          <EmptyState message={`Positions unavailable: ${positions.error}`} />
        ) : positions.data.length === 0 ? (
          <EmptyState message="No open positions." />
        ) : (
          <Table>
            <THead>
              <TR>
                <TH>Ticker</TH>
                <TH>Sector</TH>
                <TH align="right">Qty</TH>
                <TH align="right">Entry</TH>
                <TH align="right">Stop</TH>
                <TH align="right">Target</TH>
                <TH align="right">Mkt Value</TH>
                <TH align="right">Unrealized PnL</TH>
              </TR>
            </THead>
            <TBody>
              {positions.data.map((p) => (
                <TR key={p.id}>
                  <TD className="font-semibold text-zinc-100">{p.ticker}</TD>
                  <TD className="text-zinc-400">{p.sector}</TD>
                  <TD align="right" className="tabular-nums">
                    {formatNumber(p.quantity, 0)}
                  </TD>
                  <TD align="right" className="tabular-nums">
                    {formatCurrency(p.avg_entry_price)}
                  </TD>
                  <TD align="right" className="tabular-nums text-rose-300/80">
                    {formatCurrency(p.stop_price)}
                  </TD>
                  <TD
                    align="right"
                    className="tabular-nums text-emerald-300/80"
                  >
                    {formatCurrency(p.target_price)}
                  </TD>
                  <TD align="right" className="tabular-nums">
                    {formatCurrency(p.market_value)}
                  </TD>
                  <TD
                    align="right"
                    className={`tabular-nums font-medium ${pnlColor(p.unrealized_pnl)}`}
                  >
                    {formatCurrency(p.unrealized_pnl)}
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        )}
      </Card>

      {reconciliation.ok ? (
        <ReconciliationCard report={reconciliation.data} />
      ) : (
        <ApiErrorState
          title="Reconciliation unavailable"
          message={reconciliation.error}
        />
      )}
    </div>
  );
}
