import { Badge } from "@/components/ui/Badge";
import type {
  CatalystDirection,
  Sentiment,
  SignalDecision,
  TradeStatus,
} from "@/lib/types";

export function DecisionBadge({ decision }: { decision: SignalDecision }) {
  const tone =
    decision === "STRONG_BUY"
      ? "positive"
      : decision === "BUY"
        ? "info"
        : decision === "WATCH"
          ? "warning"
          : "muted";
  return <Badge tone={tone}>{decision.replace("_", " ")}</Badge>;
}

export function SentimentBadge({ sentiment }: { sentiment: Sentiment }) {
  const tone =
    sentiment === "positive"
      ? "positive"
      : sentiment === "negative"
        ? "negative"
        : "neutral";
  return <Badge tone={tone}>{sentiment}</Badge>;
}

export function CatalystDirectionBadge({
  direction,
}: {
  direction: CatalystDirection;
}) {
  const tone =
    direction === "bullish"
      ? "positive"
      : direction === "bearish"
        ? "negative"
        : "neutral";
  return <Badge tone={tone}>{direction}</Badge>;
}

export function TradeStatusBadge({ status }: { status: TradeStatus }) {
  const tone =
    status === "OPEN" ? "info" : status === "CLOSED" ? "neutral" : "muted";
  return <Badge tone={tone}>{status}</Badge>;
}
