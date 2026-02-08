import { useRef, useState, useCallback } from "react";
import type { DragEvent, ChangeEvent } from "react";
import { useAudioUpload } from "../../hooks/useAudioUpload";
import "./AudioUploader.css";

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024)
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

export function AudioUploader() {
  const { file, status, progress, uploadedPath, error, selectFile, upload, reset } =
    useAudioUpload();
  const inputRef = useRef<HTMLInputElement>(null);
  const dragCounterRef = useRef(0);
  const [isDragOver, setIsDragOver] = useState(false);

  const isUploading = status === "uploading";

  const handleFile = useCallback(
    (f: File) => {
      if (isUploading) return;
      selectFile(f);
    },
    [selectFile, isUploading],
  );

  const handleDragEnter = useCallback((e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current += 1;
    if (dragCounterRef.current === 1) {
      setIsDragOver(true);
    }
  }, []);

  const handleDragLeave = useCallback((e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current = Math.max(0, dragCounterRef.current - 1);
    if (dragCounterRef.current === 0) {
      setIsDragOver(false);
    }
  }, []);

  const handleDragOver = useCallback((e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback(
    (e: DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      dragCounterRef.current = 0;
      setIsDragOver(false);

      const droppedFile = e.dataTransfer.files[0];
      if (droppedFile) {
        handleFile(droppedFile);
      }
    },
    [handleFile],
  );

  const handleInputChange = useCallback(
    (e: ChangeEvent<HTMLInputElement>) => {
      const selected = e.target.files?.[0];
      if (selected) {
        handleFile(selected);
      }
      // 同じファイルを再選択できるようにリセット
      e.target.value = "";
    },
    [handleFile],
  );

  const handleClickZone = useCallback(() => {
    if (isUploading) return;
    inputRef.current?.click();
  }, [isUploading]);

  return (
    <section className="audio-uploader">
      <h2>音声ファイルをアップロード</h2>

      <div
        className={`drop-zone ${isDragOver ? "drop-zone--active" : ""} ${isUploading ? "drop-zone--disabled" : ""}`}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        onClick={handleClickZone}
      >
        <p className="drop-zone__text">
          ここにファイルをドラッグ&ドロップ
          <br />
          またはクリックして選択
        </p>
        <p className="drop-zone__hint">
          対応形式: mp3, wav, m4a, ogg, webm（最大 500MB）
        </p>
        <input
          ref={inputRef}
          type="file"
          accept=".mp3,.wav,.m4a,.ogg,.webm"
          className="drop-zone__input"
          onChange={handleInputChange}
        />
      </div>

      {file && (
        <div className="file-info">
          <p>
            <strong>{file.name}</strong>（{formatFileSize(file.size)}）
          </p>
        </div>
      )}

      {error && <p className="upload-message upload-message--error">{error}</p>}

      {status === "uploading" && (
        <div className="progress-bar">
          <div
            className="progress-bar__fill"
            style={{ width: `${progress}%` }}
          />
          <span className="progress-bar__text">{progress}%</span>
        </div>
      )}

      {status === "success" && uploadedPath && (
        <p className="upload-message upload-message--success">
          アップロード完了
        </p>
      )}

      <div className="upload-actions">
        {file && status !== "uploading" && status !== "success" && (
          <button className="btn btn--primary" onClick={upload}>
            アップロード
          </button>
        )}
        {(file || status === "success" || error) && status !== "uploading" && (
          <button className="btn btn--secondary" onClick={reset}>
            リセット
          </button>
        )}
      </div>
    </section>
  );
}
