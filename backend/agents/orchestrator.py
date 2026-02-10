"""Orchestrator Agent — Speech/Content Analyzer を統合"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from strands import Agent, tool
from strands.models import BedrockModel

from tools.cost_tracker import (
    AgentTokenUsage,
    calculate_total_cost,
    extract_usage_from_result,
)
from events.sse import AgentExecutionCostSummary
from .speech_analyzer import HAIKU_MODEL_ID as SPEECH_MODEL_ID, run_speech_analysis
from .content_analyzer import HAIKU_MODEL_ID as CONTENT_MODEL_ID, run_content_analysis

logger = logging.getLogger(__name__)

SONNET_MODEL_ID = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

MAX_TRANSCRIPT_LENGTH = 50_000

ORCHESTRATOR_SYSTEM_PROMPT = """\
あなたはプレゼンテーション分析のオーケストレーターです。
文字起こしテキストを受け取り、以下の手順で分析を行ってください。

## 手順
1. まず speech_analyzer ツールを使って話し方を分析してください
2. 次に content_analyzer ツールを使って内容を分析してください
3. 両方の分析結果を統合し、最終レポートを作成してください

## 統合のガイドライン
- 話し方と内容の両方から重要な点を選んでください
- 重複する指摘は統合してください
- 良い点・改善点はそれぞれ 3-5 項目にまとめてください
- サマリーは全体の総合評価として 2-3 文で記述してください

## 出力形式
必ず以下の JSON 形式のみを最終回答として返してください。JSON 以外のテキストは含めないでください。
```json
{
  "summary": "全体の総合評価（2-3文）",
  "strengths": ["良い点1", "良い点2", ...],
  "improvements": ["改善点1", "改善点2", ...]
}
```
"""


@dataclass(slots=True)
class OrchestratorResult:
    """Orchestrator の実行結果"""

    summary: str
    strengths: list[str]
    improvements: list[str]
    cost_summary: AgentExecutionCostSummary


def _parse_json_response(text: str) -> dict:
    """LLM の応答から JSON を抽出してパース"""
    # まず全体を JSON としてパース試行
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # ```json ... ``` ブロックを探す
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # { ... } を探す
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"JSON をパースできませんでした: {text[:200]}")


def _to_str_list(value: object) -> list[str]:
    """値を list[str] に正規化"""
    if not isinstance(value, list):
        return [str(value)] if value else []
    return [str(x) for x in value]


async def run_orchestrator(transcript: str) -> OrchestratorResult:
    """Orchestrator Agent を実行し、統合分析結果を返す"""
    # テキスト長制限
    if len(transcript) > MAX_TRANSCRIPT_LENGTH:
        logger.warning(
            "文字起こしテキストを %d → %d 文字に切り詰めました",
            len(transcript),
            MAX_TRANSCRIPT_LENGTH,
        )
        transcript = transcript[:MAX_TRANSCRIPT_LENGTH]

    # リクエストごとの usage 収集用（クロージャで共有）
    sub_results: dict[str, object] = {}

    @tool
    def speech_analyzer(transcript: str) -> str:
        """プレゼンテーションの話し方を分析する。文字起こしテキストから話速・フィラー・間の使い方・言い回しの明瞭さを評価する。

        Args:
            transcript: 文字起こしテキスト全文
        """
        result = run_speech_analysis(transcript)
        sub_results["speech"] = result
        return str(result)

    @tool
    def content_analyzer(transcript: str) -> str:
        """プレゼンテーションの内容を分析する。文字起こしテキストから構成・論理性・具体性・言葉遣い・メッセージの明確さを評価する。

        Args:
            transcript: 文字起こしテキスト全文
        """
        result = run_content_analysis(transcript)
        sub_results["content"] = result
        return str(result)

    agent = Agent(
        system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
        model=BedrockModel(model_id=SONNET_MODEL_ID, region_name="us-east-1"),
        callback_handler=None,
        tools=[speech_analyzer, content_analyzer],
    )

    result = await agent.invoke_async(
        f"以下のプレゼンテーションの文字起こしテキストを分析してください:\n\n{transcript}"
    )

    # --- JSON パース + 型正規化 ---
    parsed = _parse_json_response(str(result))
    summary = str(parsed.get("summary", "分析結果を取得できませんでした"))
    strengths = _to_str_list(parsed.get("strengths", []))
    improvements = _to_str_list(parsed.get("improvements", []))

    # --- コスト計算 ---
    usages: list[AgentTokenUsage] = []

    # Orchestrator 自身
    usages.append(extract_usage_from_result("orchestrator", result, SONNET_MODEL_ID))

    # サブエージェント（今回の実行で呼ばれた分のみ）
    if "speech" in sub_results:
        usages.append(extract_usage_from_result("speech_analyzer", sub_results["speech"], SPEECH_MODEL_ID))
    if "content" in sub_results:
        usages.append(extract_usage_from_result("content_analyzer", sub_results["content"], CONTENT_MODEL_ID))

    cost_summary = calculate_total_cost(usages)

    return OrchestratorResult(
        summary=summary,
        strengths=strengths,
        improvements=improvements,
        cost_summary=cost_summary,
    )
