"""Phase 4: AWS Transcribe 文字起こし統合."""

from __future__ import annotations

import asyncio
import logging
import os
from uuid import uuid4

from bedrock_agentcore import BedrockAgentCoreApp
from dotenv import load_dotenv

from events.sse import (
    AgentExecutionCostSummary,
    AnalysisEventName,
    AnalysisStatus,
    AnalysisStep,
    EventError,
    new_analysis_event,
    new_analysis_result_event,
)
from tools.transcribe import transcribe_audio

load_dotenv()

logger = logging.getLogger(__name__)

S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "")

app = BedrockAgentCoreApp()


@app.entrypoint
async def invoke(payload: dict):
    """音声ファイルを Transcribe で文字起こしし、結果を SSE で返す."""
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

    if not S3_BUCKET_NAME:
        yield new_analysis_event(
            event=AnalysisEventName.STATUS,
            run_id=run_id,
            owner_sub=owner_sub,
            status=AnalysisStatus.FAILED,
            step=AnalysisStep.UPLOAD,
            error=EventError(code="CONFIG_ERROR", detail="S3_BUCKET_NAME is not configured"),
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

    # --- Step 2: running / transcribe ---
    yield new_analysis_event(
        event=AnalysisEventName.STATUS,
        run_id=run_id,
        owner_sub=owner_sub,
        status=AnalysisStatus.RUNNING,
        step=AnalysisStep.TRANSCRIBE,
        message="音声を文字起こし中…",
    )

    try:
        result = await transcribe_audio(s3_key=s3_key, bucket=S3_BUCKET_NAME)
    except Exception as e:
        logger.exception("Transcribe エラー")
        yield new_analysis_event(
            event=AnalysisEventName.STATUS,
            run_id=run_id,
            owner_sub=owner_sub,
            status=AnalysisStatus.FAILED,
            step=AnalysisStep.TRANSCRIBE,
            error=EventError(code="TRANSCRIBE_ERROR", detail=str(e)),
        )
        return

    # キャッシュヒットの場合はメッセージを更新
    if result.cached:
        yield new_analysis_event(
            event=AnalysisEventName.STATUS,
            run_id=run_id,
            owner_sub=owner_sub,
            status=AnalysisStatus.RUNNING,
            step=AnalysisStep.TRANSCRIBE,
            message="文字起こし済みデータを使用",
        )

    # --- Step 3: running / speech（Phase 5 で実装予定、スキップ） ---
    yield new_analysis_event(
        event=AnalysisEventName.STATUS,
        run_id=run_id,
        owner_sub=owner_sub,
        status=AnalysisStatus.RUNNING,
        step=AnalysisStep.SPEECH,
        message="話し方分析をスキップ（Phase 5 で実装予定）",
    )

    # --- Step 4: partial / content ---
    preview = result.transcript[:200] + ("…" if len(result.transcript) > 200 else "")
    yield new_analysis_event(
        event=AnalysisEventName.PARTIAL,
        run_id=run_id,
        owner_sub=owner_sub,
        status=AnalysisStatus.PARTIAL,
        step=AnalysisStep.CONTENT,
        message="文字起こし完了",
        data={"partial_summary": preview},
    )
    await asyncio.sleep(0.5)

    # --- Step 5: completed / finalize ---
    # Transcribe コスト概算: $0.024/分
    transcribe_cost_usd = (result.duration_seconds / 60) * 0.024

    file_name = s3_key.rsplit("/", 1)[-1]

    yield new_analysis_result_event(
        run_id=run_id,
        owner_sub=owner_sub,
        message="文字起こしが完了しました（LLM分析は Phase 5 で実装予定）",
        summary="文字起こしが完了しました。LLM によるプレゼンテーション分析は次のフェーズで実装予定です。",
        file_name=file_name,
        file_path=s3_key,
        transcript=result.transcript,
        transcript_s3_key=result.transcript_s3_key,
        strengths=[
            "（Phase 5 で LLM が分析します）",
        ],
        improvements=[
            "（Phase 5 で LLM が分析します）",
        ],
        agent_cost=AgentExecutionCostSummary(
            total_usd=0.0,
            breakdown={
                "transcribe_usd": round(transcribe_cost_usd, 6),
            },
            is_estimated=True,
            pricing_version="phase4-v1",
        ),
    )


if __name__ == "__main__":
    app.run()
