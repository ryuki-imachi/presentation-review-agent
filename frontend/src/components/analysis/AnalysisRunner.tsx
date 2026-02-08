import { useSSEChat } from "../../hooks/useSSEChat";
import type { AnalysisEvent, AnalysisResultData, AnalysisStep } from "../../types";
import "./AnalysisRunner.css";

const STEP_LABELS: Record<AnalysisStep, string> = {
  upload: "受付",
  transcribe: "文字起こし",
  speech: "話し方分析",
  content: "内容分析",
  finalize: "結果生成",
};

const ORDERED_STEPS: AnalysisStep[] = [
  "upload",
  "transcribe",
  "speech",
  "content",
  "finalize",
];

function getLatestStep(events: AnalysisEvent[]): AnalysisStep | null {
  if (events.length === 0) return null;
  return events[events.length - 1].step;
}

function getResultData(events: AnalysisEvent[]): AnalysisResultData | null {
  for (let i = events.length - 1; i >= 0; i--) {
    const ev = events[i];
    if (ev.event === "analysis.result" && ev.data) {
      return ev.data as AnalysisResultData;
    }
  }
  return null;
}

function getLatestMessage(events: AnalysisEvent[]): string | null {
  for (let i = events.length - 1; i >= 0; i--) {
    if (events[i].message) return events[i].message!;
  }
  return null;
}

function getErrorDetail(events: AnalysisEvent[]): string | null {
  for (let i = events.length - 1; i >= 0; i--) {
    const ev = events[i];
    if (ev.error) return ev.error.detail;
  }
  return null;
}

interface Props {
  s3Key: string | null;
}

export function AnalysisRunner({ s3Key }: Props) {
  const { events, status, error, startAnalysis, reset } = useSSEChat();

  if (!s3Key) return null;

  const latestStep = getLatestStep(events);
  const latestStepIndex = latestStep
    ? ORDERED_STEPS.indexOf(latestStep)
    : -1;
  const message = getLatestMessage(events);
  const resultData = getResultData(events);
  const errorDetail = getErrorDetail(events) ?? error;

  const isIdle = status === "idle";
  const isRunning = status === "connecting" || status === "streaming";

  return (
    <section className="analysis-runner">
      <h2>プレゼンテーション分析</h2>

      {/* 分析開始ボタン */}
      {isIdle && (
        <button
          className="btn btn--primary"
          onClick={() => startAnalysis(s3Key)}
        >
          分析開始
        </button>
      )}

      {/* ステップインジケーター */}
      {(isRunning || status === "done" || status === "error") && (
        <div className="step-indicator">
          {ORDERED_STEPS.map((step, idx) => {
            let state: "pending" | "active" | "done" = "pending";
            if (idx < latestStepIndex) state = "done";
            else if (idx === latestStepIndex) {
              state = status === "done" ? "done" : "active";
            }
            return (
              <div key={step} className={`step step--${state}`}>
                <div className="step__dot" />
                <span className="step__label">{STEP_LABELS[step]}</span>
              </div>
            );
          })}
        </div>
      )}

      {/* 進捗メッセージ */}
      {isRunning && message && (
        <p className="analysis-message">{message}</p>
      )}

      {/* エラー表示 */}
      {status === "error" && errorDetail && (
        <p className="analysis-message analysis-message--error">{errorDetail}</p>
      )}

      {/* 結果表示 */}
      {status === "done" && resultData && (
        <div className="analysis-result">
          <h3>分析結果</h3>
          <p className="analysis-result__summary">{resultData.summary}</p>

          <h4>良い点</h4>
          <ul className="analysis-result__list analysis-result__list--good">
            {resultData.strengths.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>

          <h4>改善点</h4>
          <ul className="analysis-result__list analysis-result__list--improve">
            {resultData.improvements.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>

          <p className="analysis-result__cost">
            推定コスト: ${resultData.agent_cost.total_usd.toFixed(4)}
          </p>
        </div>
      )}

      {/* リセットボタン */}
      {(status === "done" || status === "error") && (
        <button className="btn btn--secondary" onClick={reset}>
          リセット
        </button>
      )}
    </section>
  );
}
