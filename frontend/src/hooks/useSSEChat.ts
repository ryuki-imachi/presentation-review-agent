import { useState, useCallback, useRef } from "react";
import { fetchAuthSession } from "aws-amplify/auth";
import outputs from "../../amplify_outputs.json";
import type { AnalysisEvent } from "../types";
import { isAnalysisEvent } from "../types/sse";

type SSEStatus = "idle" | "connecting" | "streaming" | "done" | "error";

export interface SSEChatState {
  events: AnalysisEvent[];
  status: SSEStatus;
  runId: string | null;
  error: string | null;
}

export interface SSEChatActions {
  startAnalysis: (s3Key: string) => Promise<void>;
  reset: () => void;
}

const initialState: SSEChatState = {
  events: [],
  status: "idle",
  runId: null,
  error: null,
};

/** amplify_outputs.json から AgentCore Runtime の呼び出し URL を構築 */
function getAgentCoreUrl(): string {
  const runtimeArn = (outputs as Record<string, unknown> & { custom?: { agentRuntimeArn?: string } }).custom?.agentRuntimeArn;
  if (!runtimeArn) {
    throw new Error("agentRuntimeArn が amplify_outputs.json に設定されていません。");
  }
  const region = runtimeArn.split(":")[3];
  const encodedArn = encodeURIComponent(runtimeArn);
  return `https://bedrock-agentcore.${region}.amazonaws.com/runtimes/${encodedArn}/invocations?qualifier=DEFAULT`;
}

/**
 * SSE通信でバックエンドの分析イベントを受信するカスタムフック。
 * fetch + ReadableStream で AgentCore Runtime に直接リクエスト。
 */
export function useSSEChat(): SSEChatState & SSEChatActions {
  const [state, setState] = useState<SSEChatState>(initialState);
  const abortRef = useRef<AbortController | null>(null);

  const startAnalysis = useCallback(async (s3Key: string) => {
    // 前回のリクエストがあればキャンセル
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setState({ events: [], status: "connecting", runId: null, error: null });

    try {
      // Cognito アクセストークンと owner_sub を取得
      const session = await fetchAuthSession();
      const accessToken = session.tokens?.accessToken;
      if (!accessToken) {
        throw new Error("認証トークンが取得できませんでした。再ログインしてください。");
      }
      // S3パスは identityId を使っているので、sub ではなく identityId を送る
      const ownerSub = session.identityId;
      if (!ownerSub) {
        throw new Error("identityId が取得できませんでした。再ログインしてください。");
      }

      const url = getAgentCoreUrl();
      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
          Authorization: `Bearer ${accessToken.toString()}`,
        },
        body: JSON.stringify({ s3_key: s3Key, owner_sub: ownerSub }),
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error(`サーバーエラー: ${response.status} ${response.statusText}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error("レスポンスストリームを取得できませんでした。");
      }

      setState((prev) => ({ ...prev, status: "streaming" }));

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // SSE行をパース: "data: {json}\n\n" 形式
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || trimmed.startsWith(":")) continue;

          if (trimmed.startsWith("data: ")) {
            const jsonStr = trimmed.slice(6);
            if (!jsonStr || jsonStr === "[DONE]") continue;

            try {
              const parsed: unknown = JSON.parse(jsonStr);
              if (isAnalysisEvent(parsed)) {
                setState((prev) => ({
                  ...prev,
                  events: [...prev.events, parsed],
                  runId: prev.runId ?? parsed.run_id,
                  status:
                    parsed.status === "completed" || parsed.status === "failed"
                      ? parsed.status === "completed"
                        ? "done"
                        : "error"
                      : "streaming",
                  error:
                    parsed.status === "failed" && parsed.error
                      ? parsed.error.detail
                      : prev.error,
                }));
              }
            } catch {
              // JSON パースエラーは無視（不完全なチャンクの場合）
            }
          }
        }
      }

      // ストリーム終了 — completed 受信済みなら done、未受信なら error
      setState((prev) => {
        if (prev.status !== "streaming") return prev;
        const hasCompleted = prev.events.some((e) => e.status === "completed");
        return hasCompleted
          ? { ...prev, status: "done" }
          : { ...prev, status: "error", error: "ストリームが途中で切断されました。" };
      });
    } catch (err) {
      if (controller.signal.aborted) return;
      const message =
        err instanceof Error ? err.message : "分析中にエラーが発生しました。";
      setState((prev) => ({ ...prev, status: "error", error: message }));
    }
  }, []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setState(initialState);
  }, []);

  return { ...state, startAnalysis, reset };
}
