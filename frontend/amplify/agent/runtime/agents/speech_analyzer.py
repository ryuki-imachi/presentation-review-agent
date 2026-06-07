"""Speech Analyzer サブエージェント（Haiku 4.5）"""

from __future__ import annotations

from strands import Agent
from strands.models import BedrockModel

HAIKU_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

SYSTEM_PROMPT = """\
あなたは音声特徴分析の専門家です。
与えられた書き起こしデータと音声特徴量から、
発表者の話し方について分析してください。

分析観点:
1. 話すスピード: 速すぎず遅すぎない適切なペースか
   （日本語: 300-350文字/分が目安）
2. フィラーワード: 不要な口癖が多くないか
3. 間（ポーズ）: 適切な間が取れているか

フィードバックは具体的かつ建設的に。
数値的な根拠も示してください。日本語で出力してください。

## 出力形式
必ず以下の JSON 形式のみを返してください。JSON 以外のテキストは含めないでください。
```json
{
  "feedback": "音声特徴に関するフィードバック",
  "strengths": ["強み1", "強み2", ...],
  "improvements": ["改善点1", "改善点2", ...]
}
```
"""


def run_speech_analysis(transcript: str):
    """話し方分析を実行し、Agent の結果オブジェクトを返す"""
    agent = Agent(
        system_prompt=SYSTEM_PROMPT,
        model=BedrockModel(model_id=HAIKU_MODEL_ID, region_name="us-east-1"),
        callback_handler=None,
    )
    return agent(f"以下の文字起こしテキストの話し方を分析してください:\n\n{transcript}")
