import { api } from "@/lib/api";
import { formatCurrency, formatDateTime, pnlColor } from "@/lib/format";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { StatCard } from "@/components/ui/StatCard";
import { Badge } from "@/components/ui/Badge";
import { ApiErrorState, EmptyState } from "@/components/ui/States";
import type { TradingStatus } from "@/lib/types";

export const dynamic = "force-dynamic";

function TradingStatusCard({ status }: { status: TradingStatus }) {
  const tone = status.halted ? "negative" : "positive";
  return (
    <Card className={status.halted ? "border-rose-500/30" : ""}>
      <CardHeader
        title="Trading Status"
        subtitle="Live safety state (display only)"
        action={
          <Badge tone={tone}>{status.halted ? "HALTED" : "ACTIVE"}</Badge>
        }
      />
      <CardBody className="space-y-3">
        <div className="flex items-center justify-between text-sm">
          <span className="text-zinc-400">Kill switch</span>
          <Badge tone={status.kill_switch_enabled ? "warning" : "muted"}>
            {status.kill_switch_enabled ? "ENGAGED" : "disengaged"}
          </Badge>
        </div>
        {status.halt_reason ? (
          <div className="flex items-start justify-between gap-4 text-sm">
            <span className="text-zinc-400">Halt reason</span>
            <span className="text-right text-zinc-300">
              {status.halt_reason}
            </span>
          </div>
        ) : null}
        {status.reasons.length > 0 ? (
          <div className="text-sm">
            <span className="text-zinc-400">Active reasons</span>
            <ul className="mt-2 list-inside list-disc space-y-1 text-zinc-300">
              {status.reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          </div>
        ) : (
          <p className="text-sm text-zinc-500">
            No circuit breakers active. New entries permitted.
          </p>
        )}
      </CardBody>
    </Card>
  );
}

export default async function DashboardPage() {
  const [health, integrity, tradingStatus, portfolio] = await Promise.all([
    api.getHealth(),
    api.getIntegrity(),
    api.getTradingStatus(),
    api.getPortfolio(),
  ]);

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description="System health, integrity, and live trading-safety status."
      />

      {/* Health / environment */}
      {health.ok ? (
        <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
          <StatCard
            label="API Health"
            value={health.data.status === "ok" ? "OK" : health.data.status}
            valueClassName={
              health.data.status === "ok" ? "text-emerald-400" : "text-rose-400"
            }
            hint="GET /health"
          />
          <StatCard
            label="Environment"
            value={health.data.environment}
            hint="Deployment target"
          />
          <StatCard
            label="Phase"
            value={health.data.phase}
            hint="Pipeline phase"
          />
          <StatCard
            label="Portfolio Equity"
            value={portfolio.ok ? formatCurrency(portfolio.data.equity) : "—"}
            hint={
              portfolio.ok
                ? `Cash ${formatCurrency(portfolio.data.cash)}`
                : "GET /portfolio"
            }
          />
        </div>
      ) : (
        <div className="mb-6">
          <ApiErrorState message={health.error} />
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Trading status */}
        {tradingStatus.ok ? (
          <TradingStatusCard status={tradingStatus.data} />
        ) : (
          <ApiErrorState
            title="Trading status unavailable"
            message={tradingStatus.error}
          />
        )}

        {/* System integrity */}
        {integrity.ok ? (
          <Card className={integrity.data.ok ? "" : "border-amber-500/30"}>
            <CardHeader
              title="System Integrity"
              subtitle="Trade traceability checks"
              action={
                <Badge tone={integrity.data.ok ? "positive" : "warning"}>
                  {integrity.data.ok
                    ? "OK"
                    : `${integrity.data.violations.length} ISSUES`}
                </Badge>
              }
            />
            <CardBody>
              {integrity.data.ok ? (
                <p className="text-sm text-zinc-500">
                  No orphaned documents. Every signal, trade, and AI analysis is
                  fully traceable.
                </p>
              ) : (
                <ul className="space-y-2 text-sm text-amber-300">
                  {integrity.data.violations.map((violation) => (
                    <li key={violation} className="flex gap-2">
                      <span className="text-amber-500">•</span>
                      <span>{violation}</span>
                    </li>
                  ))}
                </ul>
              )}
            </CardBody>
          </Card>
        ) : (
          <ApiErrorState
            title="Integrity check unavailable"
            message={integrity.error}
          />
        )}
      </div>

      {/* Portfolio snapshot */}
      <div className="mt-6">
        <Card>
          <CardHeader
            title="Portfolio Snapshot"
            subtitle="Account-level state"
          />
          {portfolio.ok ? (
            <CardBody>
              <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
                <Metric
                  label="Equity"
                  value={formatCurrency(portfolio.data.equity)}
                />
                <Metric
                  label="Cash"
                  value={formatCurrency(portfolio.data.cash)}
                />
                <Metric
                  label="Exposure"
                  value={formatCurrency(portfolio.data.exposure)}
                  className={pnlColor(portfolio.data.exposure)}
                />
                <Metric
                  label="Open positions"
                  value={String(portfolio.data.open_positions)}
                />
              </div>
              <p className="mt-4 text-xs text-zinc-600">
                Updated {formatDateTime(portfolio.data.updated_at)}
              </p>
            </CardBody>
          ) : (
            <EmptyState message={`Portfolio unavailable: ${portfolio.error}`} />
          )}
        </Card>
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
  className = "text-zinc-100",
}: {
  label: string;
  value: string;
  className?: string;
}) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-zinc-500">
        {label}
      </div>
      <div className={`mt-1 text-lg font-semibold tabular-nums ${className}`}>
        {value}
      </div>
    </div>
  );
}
