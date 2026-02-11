"""Strands Agent 実行コストの算出"""

from __future__ import annotations

from dataclasses import dataclass

from events.sse import AgentExecutionCostSummary

# Bedrock Cross-Region Inference 料金テーブル
# 料金確認: https://aws.amazon.com/bedrock/pricing/
# 更新手順: doc/pricing-update-guide.md を参照
PRICING: dict[str, dict[str, float]] = {
    "us.anthropic.claude-sonnet-4-5-20250929-v1:0": {
        "input_per_1m": 3.0,
        "output_per_1m": 15.0,
    },
    "us.anthropic.claude-haiku-4-5-20251001-v1:0": {
        "input_per_1m": 0.80,
        "output_per_1m": 4.0,
    },
}

PRICING_VERSION = "2026-02-10"


@dataclass(slots=True)
class AgentTokenUsage:
    """1 エージェント分のトークン使用量"""

    agent_name: str
    input_tokens: int
    output_tokens: int
    model_id: str

    @property
    def cost_usd(self) -> float:
        prices = PRICING.get(self.model_id)
        if not prices:
            return 0.0
        input_cost = (self.input_tokens / 1_000_000) * prices["input_per_1m"]
        output_cost = (self.output_tokens / 1_000_000) * prices["output_per_1m"]
        return input_cost + output_cost


def extract_usage_from_result(
    agent_name: str,
    result: object,
    model_id: str,
) -> AgentTokenUsage:
    """AgentResult.metrics.accumulated_usage からトークン数を抽出"""
    usage: dict = {}
    try:
        usage = result.metrics.accumulated_usage  # type: ignore[union-attr]
    except AttributeError:
        pass

    return AgentTokenUsage(
        agent_name=agent_name,
        input_tokens=usage.get("inputTokens", 0),
        output_tokens=usage.get("outputTokens", 0),
        model_id=model_id,
    )


def calculate_total_cost(usages: list[AgentTokenUsage]) -> AgentExecutionCostSummary:
    """全エージェントの合計コストを算出"""
    breakdown: dict[str, float] = {}
    total = 0.0
    for u in usages:
        cost = u.cost_usd
        key = f"{u.agent_name}_usd"
        breakdown[key] = round(breakdown.get(key, 0.0) + cost, 6)
        total += cost

    return AgentExecutionCostSummary(
        total_usd=round(total, 6),
        breakdown=breakdown,
        is_estimated=True,
        pricing_version=PRICING_VERSION,
    )
