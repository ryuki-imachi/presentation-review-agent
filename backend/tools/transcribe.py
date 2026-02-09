"""AWS Transcribe 文字起こし + S3 キャッシュ."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TranscribeResult:
    """文字起こし結果."""

    transcript: str
    transcript_s3_key: str
    duration_seconds: float
    cached: bool


def _derive_transcript_key(s3_key: str) -> str:
    """音声 S3 キーから文字起こしキャッシュの S3 キーを導出.

    例: private/{sub}/audio/xxx.mp3 → private/{sub}/transcripts/xxx.mp3.json
    """
    return s3_key.replace("/audio/", "/transcripts/", 1) + ".json"


def _job_name(s3_key: str) -> str:
    """S3 キーから一意なジョブ名を生成."""
    h = hashlib.sha256(s3_key.encode()).hexdigest()[:20]
    return f"pra-{h}"


def _detect_language(s3_key: str) -> str:
    """ファイル名から言語コードを推定（デフォルト: ja-JP）."""
    return "ja-JP"


async def transcribe_audio(s3_key: str, bucket: str) -> TranscribeResult:
    """S3 上の音声を Transcribe で文字起こしし、結果を S3 にキャッシュ."""
    transcript_s3_key = _derive_transcript_key(s3_key)

    s3 = boto3.client("s3")
    transcribe = boto3.client("transcribe")

    # --- キャッシュ確認 ---
    try:
        s3.head_object(Bucket=bucket, Key=transcript_s3_key)
        logger.info("キャッシュヒット: %s", transcript_s3_key)
        obj = s3.get_object(Bucket=bucket, Key=transcript_s3_key)
        cached_data = json.loads(obj["Body"].read().decode("utf-8"))
        return TranscribeResult(
            transcript=cached_data["transcript"],
            transcript_s3_key=transcript_s3_key,
            duration_seconds=cached_data.get("duration_seconds", 0.0),
            cached=True,
        )
    except ClientError as e:
        if e.response["Error"]["Code"] not in ("404", "NoSuchKey"):
            raise
        logger.info("キャッシュなし: %s → Transcribe 実行", transcript_s3_key)

    # --- Transcribe ジョブ起動 ---
    job_name = _job_name(s3_key)
    media_uri = f"s3://{bucket}/{s3_key}"
    language_code = _detect_language(s3_key)

    # Transcribe の出力先は直接 transcript_s3_key にする
    try:
        transcribe.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={"MediaFileUri": media_uri},
            LanguageCode=language_code,
            OutputBucketName=bucket,
            OutputKey=transcript_s3_key,
        )
        logger.info("Transcribe ジョブ開始: %s", job_name)
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConflictException":
            # 同名ジョブが既に存在 → ポーリングで待機
            logger.info("既存ジョブを再利用: %s", job_name)
        else:
            raise

    # --- ポーリング ---
    max_polls = 120
    poll_interval = 2
    for i in range(max_polls):
        resp = transcribe.get_transcription_job(TranscriptionJobName=job_name)
        status = resp["TranscriptionJob"]["TranscriptionJobStatus"]

        if status == "COMPLETED":
            logger.info("Transcribe ジョブ完了: %s", job_name)
            break
        elif status == "FAILED":
            reason = resp["TranscriptionJob"].get("FailureReason", "不明なエラー")
            raise RuntimeError(f"Transcribe ジョブ失敗: {reason}")
        else:
            await asyncio.sleep(poll_interval)
    else:
        raise TimeoutError(f"Transcribe ジョブがタイムアウトしました（{max_polls * poll_interval}秒）")

    # --- 結果取得 ---
    obj = s3.get_object(Bucket=bucket, Key=transcript_s3_key)
    transcribe_output = json.loads(obj["Body"].read().decode("utf-8"))

    # Transcribe 出力の JSON 構造からテキストを抽出
    results = transcribe_output.get("results", {})
    transcripts_list = results.get("transcripts", [])
    transcript_text = transcripts_list[0]["transcript"] if transcripts_list else ""

    # 音声の長さを取得（Transcribe ジョブの結果から）
    job_resp = transcribe.get_transcription_job(TranscriptionJobName=job_name)
    media_duration = 0.0
    completion_time = job_resp["TranscriptionJob"].get("CompletionTime")
    creation_time = job_resp["TranscriptionJob"].get("CreationTime")
    if completion_time and creation_time:
        # items の最後のタイムスタンプから推定
        items = results.get("items", [])
        if items:
            last_item = items[-1]
            end_time = last_item.get("end_time")
            if end_time:
                media_duration = float(end_time)

    # キャッシュ用 JSON を保存（Transcribe 生出力を上書き）
    cache_data = {
        "transcript": transcript_text,
        "duration_seconds": media_duration,
        "source_s3_key": s3_key,
    }
    s3.put_object(
        Bucket=bucket,
        Key=transcript_s3_key,
        Body=json.dumps(cache_data, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )
    logger.info("キャッシュ保存: %s", transcript_s3_key)

    return TranscribeResult(
        transcript=transcript_text,
        transcript_s3_key=transcript_s3_key,
        duration_seconds=media_duration,
        cached=False,
    )
