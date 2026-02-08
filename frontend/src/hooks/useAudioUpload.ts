import { useState, useCallback } from "react";
import { uploadData } from "aws-amplify/storage";

const ALLOWED_MIME_TYPES = new Set([
  "audio/mpeg",
  "audio/wav",
  "audio/x-wav",
  "audio/mp4",
  "audio/x-m4a",
  "audio/ogg",
  "audio/webm",
]);

const ALLOWED_EXTENSIONS = new Set([".mp3", ".wav", ".m4a", ".ogg", ".webm"]);

const MAX_FILE_SIZE = 500 * 1024 * 1024; // 500MB

type Status = "idle" | "uploading" | "success" | "error";

export interface AudioUploadState {
  file: File | null;
  status: Status;
  progress: number;
  uploadedPath: string | null;
  error: string | null;
}

export interface AudioUploadActions {
  selectFile: (file: File) => string | null;
  upload: () => Promise<void>;
  reset: () => void;
}

function getExtension(filename: string): string {
  const idx = filename.lastIndexOf(".");
  return idx >= 0 ? filename.slice(idx).toLowerCase() : "";
}

function formatTimestamp(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    date.getUTCFullYear().toString() +
    pad(date.getUTCMonth() + 1) +
    pad(date.getUTCDate()) +
    "T" +
    pad(date.getUTCHours()) +
    pad(date.getUTCMinutes()) +
    pad(date.getUTCSeconds()) +
    "Z"
  );
}

function validateFile(file: File): string | null {
  if (!ALLOWED_MIME_TYPES.has(file.type) && !ALLOWED_EXTENSIONS.has(getExtension(file.name))) {
    return "対応していないファイル形式です。mp3, wav, m4a, ogg, webm ファイルを選択してください。";
  }
  if (file.size > MAX_FILE_SIZE) {
    return "ファイルサイズが500MBを超えています。";
  }
  return null;
}

const initialState: AudioUploadState = {
  file: null,
  status: "idle",
  progress: 0,
  uploadedPath: null,
  error: null,
};

export function useAudioUpload(): AudioUploadState & AudioUploadActions {
  const [state, setState] = useState<AudioUploadState>(initialState);

  const selectFile = useCallback((file: File): string | null => {
    const validationError = validateFile(file);
    if (validationError) {
      setState((prev) => ({ ...prev, error: validationError }));
      return validationError;
    }
    setState({
      file,
      status: "idle",
      progress: 0,
      uploadedPath: null,
      error: null,
    });
    return null;
  }, []);

  const upload = useCallback(async () => {
    setState((prev) => {
      if (!prev.file) return prev;
      return { ...prev, status: "uploading", progress: 0, error: null };
    });

    // file を先に取得（setState のコールバック外で参照）
    const file = state.file;
    if (!file) return;

    const timestamp = formatTimestamp(new Date());

    try {
      const result = await uploadData({
        path: ({ identityId }) =>
          `private/${identityId}/audio/${timestamp}_${file.name}`,
        data: file,
        options: {
          onProgress: ({ transferredBytes, totalBytes }) => {
            if (totalBytes) {
              setState((prev) => ({
                ...prev,
                progress: Math.round((transferredBytes / totalBytes) * 100),
              }));
            }
          },
        },
      }).result;

      setState((prev) => ({
        ...prev,
        status: "success",
        progress: 100,
        uploadedPath: result.path,
      }));
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "アップロードに失敗しました。";
      setState((prev) => ({
        ...prev,
        status: "error",
        error: message,
      }));
    }
  }, [state.file]);

  const reset = useCallback(() => {
    setState(initialState);
  }, []);

  return { ...state, selectFile, upload, reset };
}
