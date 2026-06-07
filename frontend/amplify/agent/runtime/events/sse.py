from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
import json
from typing import Any, Mapping
from uuid import uuid4


class AnalysisStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    PARTIAL = "partial"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalysisStep(StrEnum):
    UPLOAD = "upload"
    TRANSCRIBE = "transcribe"
    SPEECH = "speech"
    CONTENT = "content"
    FINALIZE = "finalize"


class AnalysisEventName(StrEnum):
    STATUS = "analysis.status"
    PARTIAL = "analysis.partial"
    RESULT = "analysis.result"


@dataclass(slots=True)
class EventError:
    code: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "detail": self.detail}


@dataclass(slots=True)
class AgentExecutionCostSummary:
    total_usd: float
    breakdown: dict[str, float]
    is_estimated: bool = True
    pricing_version: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        if self.total_usd < 0:
            raise ValueError("total_usd must be >= 0")
        if any(value < 0 for value in self.breakdown.values()):
            raise ValueError("breakdown values must be >= 0")

        return {
            "total_usd": round(self.total_usd, 6),
            "breakdown": {key: round(value, 6) for key, value in self.breakdown.items()},
            "is_estimated": self.is_estimated,
            "pricing_version": self.pricing_version,
        }


def utc_now_iso8601() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_analysis_event(
    *,
    event: AnalysisEventName,
    run_id: str,
    owner_sub: str,
    status: AnalysisStatus,
    step: AnalysisStep,
    message: str | None = None,
    data: dict[str, Any] | None = None,
    error: EventError | None = None,
    event_id: str | None = None,
    emitted_at: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "event": event.value,
        "id": event_id or f"evt_{uuid4()}",
        "run_id": run_id,
        "owner_sub": owner_sub,
        "status": status.value,
        "step": step.value,
        "emitted_at": emitted_at or utc_now_iso8601(),
    }
    if message:
        payload["message"] = message
    if data is not None:
        payload["data"] = data
    if error is not None:
        payload["error"] = error.to_dict()

    return payload


def new_analysis_result_event(
    *,
    run_id: str,
    owner_sub: str,
    summary: str,
    strengths: list[dict] | list[str],
    improvements: list[dict] | list[str],
    detailed_feedback: str = "",
    agent_cost: AgentExecutionCostSummary,
    file_name: str | None = None,
    file_path: str | None = None,
    transcript: str | None = None,
    transcript_s3_key: str | None = None,
    message: str | None = None,
    event_id: str | None = None,
    emitted_at: str | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "summary": summary,
        "strengths": strengths,
        "improvements": improvements,
        "detailed_feedback": detailed_feedback,
        "agent_cost": agent_cost.to_dict(),
    }
    if file_name is not None:
        data["file_name"] = file_name
    if file_path is not None:
        data["file_path"] = file_path
    if transcript is not None:
        data["transcript"] = transcript
    if transcript_s3_key is not None:
        data["transcript_s3_key"] = transcript_s3_key
    return new_analysis_event(
        event=AnalysisEventName.RESULT,
        run_id=run_id,
        owner_sub=owner_sub,
        status=AnalysisStatus.COMPLETED,
        step=AnalysisStep.FINALIZE,
        message=message,
        data=data,
        event_id=event_id,
        emitted_at=emitted_at,
    )


def format_sse_message(payload: Mapping[str, Any]) -> str:
    event_name = payload.get("event")
    if not isinstance(event_name, str) or not event_name:
        raise ValueError("payload.event is required")

    lines: list[str] = []

    event_id = payload.get("id")
    if isinstance(event_id, str) and event_id:
        lines.append(f"id: {event_id}")

    lines.append(f"event: {event_name}")
    lines.append(f"data: {json.dumps(dict(payload), ensure_ascii=False)}")
    lines.append("")
    return "\n".join(lines)


def format_error_event(
    *,
    run_id: str,
    owner_sub: str,
    step: AnalysisStep,
    code: str,
    detail: str,
    event_id: str | None = None,
) -> str:
    payload = new_analysis_event(
        event=AnalysisEventName.STATUS,
        run_id=run_id,
        owner_sub=owner_sub,
        status=AnalysisStatus.FAILED,
        step=step,
        error=EventError(code=code, detail=detail),
        event_id=event_id,
    )
    return format_sse_message(payload)


def assert_event_ownership(*, request_sub: str, owner_sub: str) -> None:
    if request_sub != owner_sub:
        raise PermissionError("forbidden: run_id does not belong to request user")
