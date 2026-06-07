"""Content Analyzer サブエージェント（Haiku 4.5）"""

from __future__ import annotations

from strands import Agent
from strands.models import BedrockModel

HAIKU_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

SYSTEM_PROMPT = """\
あなたはプレゼンテーション内容の分析専門家です。
書き起こしテキストから、発表の構成と言葉遣いを評価してください。

分析観点:
1. 構成: イントロ→本題→まとめの流れがあるか
2. 論理性: 話の繋がりが自然か、トピック遷移がスムーズか
3. 言葉遣い: わかりやすい表現か、専門用語は適切か
4. 時間配分: イントロ・本題・まとめのバランス

プレゼンテーションの「伝わりやすさ」を重視して評価してください。
日本語で出力してください。

## 出力形式
必ず以下の JSON 形式のみを返してください。JSON 以外のテキストは含めないでください。
```json
{
  "structure": {
    "has_intro": true,
    "has_conclusion": true,
    "feedback": "構成に関するフィードバック"
  },
  "language": {
    "clarity": "high/medium/low",
    "feedback": "言葉遣いに関するフィードバック"
  },
  "strengths": ["強み1", "強み2", ...],
  "improvements": ["改善点1", "改善点2", ...]
}
```
"""


def run_content_analysis(transcript: str):
    """内容分析を実行し、Agent の結果オブジェクトを返す"""
    agent = Agent(
        system_prompt=SYSTEM_PROMPT,
        model=BedrockModel(model_id=HAIKU_MODEL_ID, region_name="us-east-1"),
        callback_handler=None,
    )
    return agent(f"以下の文字起こしテキストの内容を分析してください:\n\n{transcript}")
