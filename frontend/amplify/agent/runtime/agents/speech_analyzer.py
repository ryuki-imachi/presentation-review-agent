"""Speech Analyzer サブエージェント（Haiku 4.5）"""

from __future__ import annotations

from strands import Agent
from strands.models import BedrockModel

HAIKU_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

SYSTEM_PROMPT = """\
あなたはプレゼンテーションの「話し方」を分析する専門家です。
与えられた文字起こしテキストから、以下の観点で分析してください。

## 分析観点
1. **話速**: テキストの密度や文の長さから推定される話速の適切さ
2. **フィラー**: 「えー」「あの」「まあ」「えっと」などの不要語の頻度
3. **間の使い方**: 句読点やフレーズの切れ目から推定される間の取り方
4. **言い回しの明瞭さ**: 曖昧表現、二重否定、冗長表現の有無

注意: 文字起こしテキストのみの入力であるため、声のトーンや抑揚など音声的な特徴は分析対象外です。
テキストから推定可能な範囲に限定して分析してください。

## 出力形式
必ず以下の JSON 形式のみを返してください。JSON 以外のテキストは含めないでください。
```json
{
  "speech_strengths": ["良い点1", "良い点2", ...],
  "speech_improvements": ["改善点1", "改善点2", ...],
  "speech_summary": "話し方の総合評価（1-2文）"
}
```
各リストは 2-4 項目にしてください。
"""


def run_speech_analysis(transcript: str):
    """話し方分析を実行し、Agent の結果オブジェクトを返す"""
    agent = Agent(
        system_prompt=SYSTEM_PROMPT,
        model=BedrockModel(model_id=HAIKU_MODEL_ID, region_name="us-east-1"),
        callback_handler=None,
    )
    return agent(f"以下の文字起こしテキストの話し方を分析してください:\n\n{transcript}")
