import { useState, useCallback } from "react";
import { remove } from "aws-amplify/storage";

type Status = "idle" | "deleting" | "done" | "error";

export interface FileDeleteState {
  status: Status;
  error: string | null;
}

export interface FileDeleteActions {
  deleteFiles: (paths: string[]) => Promise<boolean>;
  reset: () => void;
}

export function useFileDelete(): FileDeleteState & FileDeleteActions {
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);

  const deleteFiles = useCallback(async (paths: string[]): Promise<boolean> => {
    if (paths.length === 0) return true;

    setStatus("deleting");
    setError(null);

    try {
      await Promise.all(
        paths.map((path) => remove({ path })),
      );
      setStatus("done");
      return true;
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "ファイルの削除に失敗しました。";
      setStatus("error");
      setError(message);
      return false;
    }
  }, []);

  const reset = useCallback(() => {
    setStatus("idle");
    setError(null);
  }, []);

  return { status, error, deleteFiles, reset };
}
