export const ANALYSIS_STATUSES = [
  "queued",
  "running",
  "partial",
  "completed",
  "failed",
] as const;

export const ANALYSIS_STEPS = [
  "upload",
  "transcribe",
  "speech",
  "content",
  "finalize",
] as const;

export const ANALYSIS_EVENT_NAMES = [
  "analysis.status",
  "analysis.partial",
  "analysis.result",
] as const;

export type AnalysisStatus = (typeof ANALYSIS_STATUSES)[number];
export type AnalysisStep = (typeof ANALYSIS_STEPS)[number];
export type AnalysisEventName = (typeof ANALYSIS_EVENT_NAMES)[number];

export type EventError = {
  code: string;
  detail: string;
};

export type BaseAnalysisEvent = {
  event: AnalysisEventName;
  id?: string;
  run_id: string;
  owner_sub: string;
  status: AnalysisStatus;
  step: AnalysisStep;
  emitted_at: string;
  message?: string;
  data?: Record<string, unknown>;
  error?: EventError;
};

export type AnalysisStatusEvent = BaseAnalysisEvent & {
  event: "analysis.status";
};

export type AnalysisPartialData = {
  partial_summary?: string;
  [key: string]: unknown;
};

export type AnalysisPartialEvent = BaseAnalysisEvent & {
  event: "analysis.partial";
  status: "partial";
  data?: AnalysisPartialData;
};

export type AnalysisResultData = {
  summary: string;
  strengths: string[];
  improvements: string[];
  agent_cost: AgentExecutionCost;
  file_name?: string;
  file_path?: string;
  [key: string]: unknown;
};

export type AgentExecutionCostBreakdown = {
  orchestrator_usd?: number;
  speech_analyzer_usd?: number;
  content_analyzer_usd?: number;
  [key: string]: number | undefined;
};

export type AgentExecutionCost = {
  total_usd: number;
  breakdown: AgentExecutionCostBreakdown;
  is_estimated: boolean;
  pricing_version: string;
};

export type AnalysisResultEvent = BaseAnalysisEvent & {
  event: "analysis.result";
  status: "completed";
  step: "finalize";
  data: AnalysisResultData;
};

export type AnalysisEvent =
  | AnalysisStatusEvent
  | AnalysisPartialEvent
  | AnalysisResultEvent;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isEnumValue<T extends readonly string[]>(
  source: T,
  value: unknown,
): value is T[number] {
  return typeof value === "string" && source.includes(value);
}

export function isAnalysisEvent(value: unknown): value is AnalysisEvent {
  if (!isRecord(value)) return false;

  if (!isEnumValue(ANALYSIS_EVENT_NAMES, value.event)) return false;
  if (!isEnumValue(ANALYSIS_STATUSES, value.status)) return false;
  if (!isEnumValue(ANALYSIS_STEPS, value.step)) return false;
  if (typeof value.run_id !== "string" || value.run_id.length === 0) return false;
  if (typeof value.owner_sub !== "string" || value.owner_sub.length === 0)
    return false;
  if (typeof value.emitted_at !== "string" || value.emitted_at.length === 0)
    return false;

  if (value.id !== undefined && typeof value.id !== "string") return false;
  if (value.message !== undefined && typeof value.message !== "string")
    return false;

  if (value.error !== undefined) {
    if (!isRecord(value.error)) return false;
    if (typeof value.error.code !== "string") return false;
    if (typeof value.error.detail !== "string") return false;
  }

  if (value.event === "analysis.partial") {
    if (value.status !== "partial") return false;
    if (value.data !== undefined) {
      if (!isRecord(value.data)) return false;
      if (
        value.data.partial_summary !== undefined &&
        typeof value.data.partial_summary !== "string"
      )
        return false;
    }
  }

  if (value.event === "analysis.result") {
    if (value.status !== "completed" || value.step !== "finalize") return false;
    if (!isRecord(value.data)) return false;
    if (typeof value.data.summary !== "string") return false;
    if (
      !Array.isArray(value.data.strengths) ||
      !value.data.strengths.every((item) => typeof item === "string")
    ) {
      return false;
    }
    if (
      !Array.isArray(value.data.improvements) ||
      !value.data.improvements.every((item) => typeof item === "string")
    ) {
      return false;
    }

    if (!isRecord(value.data.agent_cost)) return false;
    if (!isNumber(value.data.agent_cost.total_usd)) return false;
    if (!isRecord(value.data.agent_cost.breakdown)) return false;
    if (
      Object.values(value.data.agent_cost.breakdown).some(
        (item) => item !== undefined && !isNumber(item),
      )
    ) {
      return false;
    }
    if (typeof value.data.agent_cost.is_estimated !== "boolean") return false;
    if (typeof value.data.agent_cost.pricing_version !== "string") return false;
  }

  return true;
}
