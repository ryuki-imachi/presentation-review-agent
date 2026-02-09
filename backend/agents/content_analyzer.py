"""Content Analyzer サブエージェント（Haiku 4.5）"""

from __future__ import annotations

from strands import Agent, tool
from strands.models import BedrockModel

HAIKU_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

SYSTEM_PROMPT = """\
あなたはプレゼンテーションの「内容」を分析する専門家です。
与えられた文字起こしテキストから、以下の観点で分析してください。

## 分析観点
1. **構成**: 導入・本論・結論の構成が適切か
2. **論理性**: 主張と根拠の整合性、論理的な流れ
3. **具体性**: 具体例やデータの使用
4. **言葉遣い**: 専門用語の適切さ、聴衆に合った表現レベル
5. **メッセージの明確さ**: 結論や要点が明確に伝わるか

## 出力形式
必ず以下の JSON 形式のみを返してください。JSON 以外のテキストは含めないでください。
```json
{
  "content_strengths": ["良い点1", "良い点2", ...],
  "content_improvements": ["改善点1", "改善点2", ...],
  "content_summary": "内容の総合評価（1-2文）"
}
```
各リストは 2-4 項目にしてください。
"""

# モジュールレベルで最後の実行結果を保持（コスト追跡用）
_last_result = None


@tool
def content_analyzer(transcript: str) -> str:
    """プレゼンテーションの内容を分析する。文字起こしテキストから構成・論理性・具体性・言葉遣い・メッセージの明確さを評価する。

    Args:
        transcript: 文字起こしテキスト全文
    """
    global _last_result
    agent = Agent(
        system_prompt=SYSTEM_PROMPT,
        model=BedrockModel(model_id=HAIKU_MODEL_ID, region_name="us-east-1"),
        callback_handler=None,
    )
    _last_result = agent(f"以下の文字起こしテキストの内容を分析してください:\n\n{transcript}")
    return str(_last_result)


def get_last_result():
    """最後の実行結果を返す（コスト追跡用）"""
    return _last_result
