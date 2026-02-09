import { useEffect } from "react";
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

function buildMarkdown(resultData: AnalysisResultData, runId: string | null): string {
  const lines: string[] = [];
  lines.push("# プレゼンテーション分析レポート");
  lines.push("");
  if (resultData.file_name) {
    lines.push(`**ファイル**: ${resultData.file_name}`);
  }
  if (runId) {
    lines.push(`**Run ID**: ${runId}`);
  }
  lines.push("");
  lines.push("## サマリー");
  lines.push(resultData.summary);
  lines.push("");
  lines.push("## 良い点");
  for (const s of resultData.strengths) {
    lines.push(`- ${s}`);
  }
  lines.push("");
  lines.push("## 改善点");
  for (const s of resultData.improvements) {
    lines.push(`- ${s}`);
  }
  if (resultData.transcript) {
    lines.push("");
    lines.push("## 文字起こし全文");
    lines.push(resultData.transcript);
  }
  lines.push("");
  lines.push(`---`);
  lines.push(`推定コスト: $${resultData.agent_cost.total_usd.toFixed(4)}`);
  return lines.join("\n");
}

function handleDownload(resultData: AnalysisResultData, runId: string | null) {
  const md = buildMarkdown(resultData, runId);
  const blob = new Blob([md], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `analysis-report-${runId ?? "unknown"}.md`;
  a.click();
  URL.revokeObjectURL(url);
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
  const { events, status, error, runId, startAnalysis, reset } = useSSEChat();

  useEffect(() => reset(), [s3Key, reset]);

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
          {resultData.file_name && (
            <p className="analysis-result__file">{resultData.file_name}</p>
          )}
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

          {resultData.transcript && (
            <details className="analysis-result__transcript">
              <summary>文字起こし全文を表示</summary>
              <pre className="analysis-result__transcript-text">
                {resultData.transcript}
              </pre>
            </details>
          )}

          <p className="analysis-result__cost">
            推定コスト: ${resultData.agent_cost.total_usd.toFixed(4)}
          </p>
        </div>
      )}

      {/* アクションボタン */}
      {(status === "done" || status === "error") && (
        <div className="analysis-actions">
          {status === "done" && resultData && (
            <button
              className="btn btn--primary"
              onClick={() => handleDownload(resultData, runId)}
            >
              レポートをダウンロード
            </button>
          )}
          <button className="btn btn--secondary" onClick={reset}>
            リセット
          </button>
        </div>
      )}
    </section>
  );
}
