"""Phase 3: エコーエージェント — SSE疎通確認用."""

from __future__ import annotations

import asyncio
from uuid import uuid4

from bedrock_agentcore import BedrockAgentCoreApp

from events.sse import (
    AgentExecutionCostSummary,
    AnalysisEventName,
    AnalysisStatus,
    AnalysisStep,
    EventError,
    new_analysis_event,
    new_analysis_result_event,
)

app = BedrockAgentCoreApp()


@app.entrypoint
async def invoke(payload: dict):
    """エコーエージェント: モックイベントをSSEで段階的に返す."""
    s3_key: str = payload.get("s3_key", "")
    owner_sub: str = payload.get("owner_sub", "")
    run_id = str(uuid4())

    # --- バリデーション ---
    if not s3_key or not owner_sub:
        yield new_analysis_event(
            event=AnalysisEventName.STATUS,
            run_id=run_id,
            owner_sub=owner_sub or "unknown",
            status=AnalysisStatus.FAILED,
            step=AnalysisStep.UPLOAD,
            error=EventError(code="INVALID_PAYLOAD", detail="s3_key and owner_sub are required"),
        )
        return

    expected_prefix = f"private/{owner_sub}/"
    if not s3_key.startswith(expected_prefix):
        yield new_analysis_event(
            event=AnalysisEventName.STATUS,
            run_id=run_id,
            owner_sub=owner_sub,
            status=AnalysisStatus.FAILED,
            step=AnalysisStep.UPLOAD,
            error=EventError(code="FORBIDDEN", detail="s3_key does not belong to owner_sub"),
        )
        return

    # --- Step 1: queued / upload ---
    yield new_analysis_event(
        event=AnalysisEventName.STATUS,
        run_id=run_id,
        owner_sub=owner_sub,
        status=AnalysisStatus.QUEUED,
        step=AnalysisStep.UPLOAD,
        message="ファイルを受け付けました",
    )
    await asyncio.sleep(1)

    # --- Step 2: running / transcribe ---
    yield new_analysis_event(
        event=AnalysisEventName.STATUS,
        run_id=run_id,
        owner_sub=owner_sub,
        status=AnalysisStatus.RUNNING,
        step=AnalysisStep.TRANSCRIBE,
        message="音声を文字起こし中…",
    )
    await asyncio.sleep(1)

    # --- Step 3: partial / content ---
    yield new_analysis_event(
        event=AnalysisEventName.PARTIAL,
        run_id=run_id,
        owner_sub=owner_sub,
        status=AnalysisStatus.PARTIAL,
        step=AnalysisStep.CONTENT,
        message="内容を分析中…",
        data={"partial_summary": "プレゼンテーションの構成を分析しています…"},
    )
    await asyncio.sleep(1)

    # --- Step 4: completed / finalize ---
    yield new_analysis_result_event(
        run_id=run_id,
        owner_sub=owner_sub,
        message="分析が完了しました",
        summary="エコーエージェントによるモック分析結果です。",
        file_name=s3_key.rsplit("/", 1)[-1],
        file_path=s3_key,
        strengths=[
            "明確な導入部でテーマを提示している",
            "データを用いた根拠のある説明",
            "適切なスライド枚数",
        ],
        improvements=[
            "結論スライドをより具体的にする",
            "聴衆への問いかけを増やす",
            "専門用語の補足説明を追加する",
        ],
        agent_cost=AgentExecutionCostSummary(
            total_usd=0.0,
            breakdown={"echo_agent_usd": 0.0},
            is_estimated=True,
            pricing_version="echo-v0",
        ),
    )


if __name__ == "__main__":
    app.run()
