"""Phase 5: Strands Agent によるプレゼンテーション LLM 分析"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from uuid import uuid4

from bedrock_agentcore import BedrockAgentCoreApp
from dotenv import load_dotenv

from logging_config import setup_logging

from events.sse import (
    AnalysisEventName,
    AnalysisStatus,
    AnalysisStep,
    EventError,
    new_analysis_event,
    new_analysis_result_event,
)
from agents import run_orchestrator
from tools.transcribe import transcribe_audio

load_dotenv()
setup_logging()

logger = logging.getLogger(__name__)

S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "")

app = BedrockAgentCoreApp()


@app.entrypoint
async def invoke(payload: dict):
    """音声ファイルを Transcribe で文字起こしし、Strands Agent で分析"""
    s3_key: str = payload.get("s3_key", "")
    owner_sub: str = payload.get("owner_sub", "")
    run_id = str(uuid4())
    start_time = time.monotonic()

    logger.info("分析リクエスト受付", extra={"run_id": run_id, "owner_sub": owner_sub, "s3_key": s3_key})

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
        logger.exception("Transcribe エラー", extra={"run_id": run_id, "owner_sub": owner_sub})
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

    # --- Step 3: running / speech ---
    yield new_analysis_event(
        event=AnalysisEventName.STATUS,
        run_id=run_id,
        owner_sub=owner_sub,
        status=AnalysisStatus.RUNNING,
        step=AnalysisStep.SPEECH,
        message="話し方を分析中…",
    )

    # --- Orchestrator Agent 実行（speech + content 統合） ---
    try:
        orch_result = await run_orchestrator(result.transcript)
    except Exception as e:
        logger.exception("エージェント分析エラー", extra={"run_id": run_id, "owner_sub": owner_sub})
        yield new_analysis_event(
            event=AnalysisEventName.STATUS,
            run_id=run_id,
            owner_sub=owner_sub,
            status=AnalysisStatus.FAILED,
            step=AnalysisStep.SPEECH,
            error=EventError(code="AGENT_ERROR", detail=str(e)),
        )
        return

    # --- Step 4: running / content ---
    yield new_analysis_event(
        event=AnalysisEventName.STATUS,
        run_id=run_id,
        owner_sub=owner_sub,
        status=AnalysisStatus.RUNNING,
        step=AnalysisStep.CONTENT,
        message="内容分析が完了しました",
    )

    # --- partial / content ---
    preview = orch_result.summary[:200] + ("…" if len(orch_result.summary) > 200 else "")
    yield new_analysis_event(
        event=AnalysisEventName.PARTIAL,
        run_id=run_id,
        owner_sub=owner_sub,
        status=AnalysisStatus.PARTIAL,
        step=AnalysisStep.CONTENT,
        message="分析完了",
        data={"partial_summary": preview},
    )
    await asyncio.sleep(0.5)

    # --- Step 5: completed / finalize ---
    elapsed = time.monotonic() - start_time
    file_name = s3_key.rsplit("/", 1)[-1]

    logger.info(
        "分析完了",
        extra={
            "run_id": run_id,
            "owner_sub": owner_sub,
            "elapsed_seconds": round(elapsed, 2),
            "total_cost_usd": orch_result.cost_summary.total_usd,
            "cached_transcript": result.cached,
        },
    )

    yield new_analysis_result_event(
        run_id=run_id,
        owner_sub=owner_sub,
        message="プレゼンテーション分析が完了しました",
        summary=orch_result.summary,
        file_name=file_name,
        file_path=s3_key,
        transcript=result.transcript,
        transcript_s3_key=result.transcript_s3_key,
        strengths=orch_result.strengths,
        improvements=orch_result.improvements,
        agent_cost=orch_result.cost_summary,
    )


if __name__ == "__main__":
    app.run()
