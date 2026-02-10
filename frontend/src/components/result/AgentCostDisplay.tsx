import type { AgentExecutionCost } from "../../types";
import "./Result.css";

interface Props {
  cost: AgentExecutionCost;
}

const LABELS: Record<string, string> = {
  orchestrator_usd: "Orchestrator",
  speech_analyzer_usd: "話し方分析",
  content_analyzer_usd: "内容分析",
};

export function AgentCostDisplay({ cost }: Props) {
  const breakdownEntries = Object.entries(cost.breakdown).filter(
    ([, v]) => v !== undefined,
  ) as [string, number][];

  return (
    <details className="cost-display">
      <summary className="cost-display__summary">
        推定コスト: ${cost.total_usd.toFixed(4)}
        {cost.is_estimated && " (概算)"}
      </summary>
      <div className="cost-display__breakdown">
        {breakdownEntries.map(([key, value]) => (
          <div key={key} className="cost-display__breakdown-item">
            <span className="cost-display__breakdown-label">
              {LABELS[key] ?? key}
            </span>
            <span>${value.toFixed(4)}</span>
          </div>
        ))}
      </div>
    </details>
  );
}
