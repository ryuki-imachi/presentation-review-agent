# 開発進捗メモ

## 全体計画
設計書: `doc/basic_design.md` の7フェーズに沿って開発を進める。

## Phase 1: 基盤構築（React + Vite + Cognito認証）— 完了

### 実装手順
1. `frontend/` にVite + React + TypeScriptプロジェクトを初期化
2. Amplify Gen2パッケージをインストール（aws-amplify, @aws-amplify/ui-react, @aws-amplify/backend, @aws-amplify/backend-cli）
3. Amplifyバックエンドリソース定義ファイルを作成
   - `frontend/amplify/auth/resource.ts` — Cognito認証（メールログイン）
   - `frontend/amplify/storage/resource.ts` — S3ストレージ（private/{entity_id}/* アクセス制御）
   - `frontend/amplify/backend.ts` — auth + storage 統合
4. フロントエンドエントリーポイント修正
   - `frontend/src/main.tsx` — Amplify.configure + CSS import
   - `frontend/src/App.tsx` — Authenticatorコンポーネントでログイン/ログアウト
5. .gitignore更新（amplify_outputs.json, node_modules, .amplify）
6. 既存SSE型定義（`frontend/src/types/`）を保持

### 完了条件
- ブラウザでサインアップ → メール確認 → ログイン → ログアウトが動作する

### PR
`feature/phase1-auth-setup` ブランチでPR作成

---

## Phase 2: ストレージ & 音声アップロード — 完了

### Context
Phase 1 完了済み。Amplify Storage リソース定義（`private/{entity_id}/*`）は Phase 1 で作成済み。
Phase 2 では音声ファイルのS3アップロード機能を追加する。
**完了条件**: 音声ファイルがS3に保存される。

### 実装手順
1. `frontend/src/hooks/useAudioUpload.ts` を新規作成
   - ステート: `file`, `status`（idle/uploading/success/error）, `progress`（0-100）, `uploadedPath`, `error`
   - アクション: `selectFile`（バリデーション付き）, `upload`（S3送信）, `reset`
   - バリデーション:
     - MIMEタイプ: `audio/mpeg`, `audio/wav`, `audio/x-wav`, `audio/mp4`, `audio/x-m4a`, `audio/ogg`, `audio/webm`
     - 拡張子フォールバック: `.mp3`, `.wav`, `.m4a`, `.ogg`, `.webm`（ブラウザ間のMIME差異対策）
     - 最大サイズ: 500MB
   - S3キー: `private/${identityId}/audio/${timestamp}_${filename}`
     - タイムスタンプ形式: `20260208T101530Z`（ISO 8601 basic format）
   - Amplify API: `uploadData` の `path` は関数形式 `({ identityId }) => ...` を使用
   - 進捗: `options.onProgress` コールバックで `transferredBytes / totalBytes` を計算

2. `frontend/src/components/upload/AudioUploader.tsx` + `.css` を新規作成
   - `useAudioUpload` フックを内部で使用
   - ドロップゾーン: 点線ボーダー、ドラッグ中ハイライト（`useRef<number>` カウンターでバブリング対策）
   - ファイル選択: hidden `<input type="file" accept=".mp3,.wav,.m4a,.ogg,.webm">`
   - 進捗バー: `status === "uploading"` のとき表示
   - 状態表示: ファイル名・サイズ、成功メッセージ、エラーメッセージ
   - `formatFileSize` ヘルパーはコンポーネント内にローカル定義

3. `frontend/src/components/upload/index.ts` を新規作成（barrel export）

4. `frontend/src/App.tsx` を変更 — `<AudioUploader />` を追加

### 対象ファイル一覧
| ファイル | 操作 |
|---|---|
| `frontend/src/hooks/useAudioUpload.ts` | 新規作成 |
| `frontend/src/components/upload/AudioUploader.tsx` | 新規作成 |
| `frontend/src/components/upload/AudioUploader.css` | 新規作成 |
| `frontend/src/components/upload/index.ts` | 新規作成 |
| `frontend/src/App.tsx` | 変更 |

### 設計判断
- FileDropZone を独立コンポーネントにしない（YAGNI）
- common/Button, common/Card は作らない（Phase 6 の範囲）
- 500MB上限（プレゼン音声WAV非圧縮60分≒600MB）
- tsconfig の `verbatimModuleSyntax: true` に注意（型のみの import は `import type` を使用）

### 検証方法
1. DevContainer内で `npx ampx sandbox` が起動済みであること
2. `npm run dev` でVite開発サーバーを起動
3. ブラウザでログイン後、音声ファイルをドラッグ&ドロップまたはファイル選択
4. プログレスバーが表示され、アップロード完了メッセージが出ること
5. AWSコンソールのS3で `private/{identityId}/audio/{timestamp}_{filename}` にファイルが保存されていること

### PR
`feature/phase2-audio-upload` ブランチでPR作成

---

## Phase 3: バックエンド最小構成（AgentCore デプロイ）— 完了

### Context
Phase 1-2 完了。ログイン + S3 音声アップロードが動作する状態。
Phase 3 では AgentCore Runtime にエコーエージェントをデプロイし、フロントエンドからSSEで疎通確認する。
**完了条件**: フロントエンドからAgentCoreにメッセージを送り、SSEで逐次応答が返る。

### アーキテクチャ

```
[ブラウザ]
  ↓ POST /api/analyze { s3_key, owner_sub }
  ↓ Authorization: Bearer <Cognito ID Token>
[Vite dev proxy]                    ← 開発時のみ。CORS回避
  ↓ proxy → localhost:8080 or AgentCore endpoint
[AgentCore Runtime / agentcore dev]
  ↓ JWT検証（デプロイ時のみ）
[backend/main.py エコーエージェント]
  ↓ SSE: data: {JSON}\n\n を複数回 yield
[ブラウザ]
  ↓ fetch + ReadableStream でパース
  ↓ isAnalysisEvent() で検証
[useSSEChat フック → AnalysisRunner コンポーネント]
```

### 実装手順

#### バックエンド

1. `backend/main.py` を新規作成 — エコーエージェントのエントリーポイント
   - `BedrockAgentCoreApp` でアプリ初期化、`@app.entrypoint` でハンドラ定義
   - payload: `{ "s3_key": string, "owner_sub": string }`
   - `run_id` を UUID で生成
   - `s3_key` が `private/{owner_sub}/` で始まることを検証（所有者照合）
   - 既存の `events.sse` ヘルパーを使い、以下の順にイベントを yield:
     1. `analysis.status` — queued / upload
     2. `analysis.status` — running / transcribe
     3. `analysis.partial` — partial / content（モック部分サマリ）
     4. `analysis.result` — completed / finalize（モック結果 + `AgentExecutionCostSummary`）
   - 各ステップ間に `asyncio.sleep(1)` で遅延（SSEストリーミングの動作確認用）
   - **`format_sse_message` は使わない**: AgentCore が yield した dict を自動的に SSE `data:` にラップ

2. `backend/.bedrock_agentcore.yaml` を新規作成 — Starter Toolkit 設定
   ```yaml
   runtime:
     name: presentation-review-agent
     entry_point: main.py
   ```

3. `backend/requirements.txt` を新規作成 — コンテナ用依存関係

#### フロントエンド

4. `frontend/src/hooks/useSSEChat.ts` を新規作成 — SSE通信フック
   - ステート: `events`（AnalysisEvent[]）, `status`（idle/connecting/streaming/done/error）, `runId`, `error`
   - アクション: `startAnalysis(s3Key)`, `reset()`
   - 処理フロー:
     1. `fetchAuthSession()` で Cognito ID Token 取得
     2. `fetch('/api/analyze', { POST, Bearer token, body: { s3_key, owner_sub } })`
     3. `response.body.getReader()` で ReadableStream 取得
     4. SSE パース: `data:` プレフィックス除去 → JSON.parse → `isAnalysisEvent()` 検証
     5. `completed` or `failed` でストリーム終了
   - EventSource は POST 非対応のため fetch + ReadableStream を使用

5. `frontend/src/components/analysis/AnalysisRunner.tsx` + `.css` を新規作成
   - props: `s3Key: string | null`
   - 「分析開始」ボタン + 進捗ステップ表示 + 結果表示 + エラー表示

6. `frontend/src/components/analysis/index.ts` を新規作成（barrel export）

7. `frontend/vite.config.ts` を変更 — dev proxy 追加
   - `/api/analyze` → `http://localhost:8080/invocations` にプロキシ

8. `frontend/src/App.tsx` を変更
   - `useAudioUpload` を App レベルで使用
   - `uploadedPath` を `AudioUploader` と `AnalysisRunner` で共有

9. `frontend/src/components/upload/AudioUploader.tsx` を変更（props化）

### 対象ファイル一覧
| ファイル | 操作 |
|---|---|
| `backend/main.py` | 新規作成 |
| `backend/.bedrock_agentcore.yaml` | 新規作成 |
| `backend/requirements.txt` | 新規作成 |
| `frontend/src/hooks/useSSEChat.ts` | 新規作成 |
| `frontend/src/components/analysis/AnalysisRunner.tsx` | 新規作成 |
| `frontend/src/components/analysis/AnalysisRunner.css` | 新規作成 |
| `frontend/src/components/analysis/index.ts` | 新規作成 |
| `frontend/vite.config.ts` | 変更 |
| `frontend/src/App.tsx` | 変更 |
| `frontend/src/components/upload/AudioUploader.tsx` | 変更（props化） |

### 設計判断
- **エコーエージェントに Strands Agent は使わない**: Phase 3 は SSE 疎通確認が目的。実際の LLM 呼び出しは Phase 4-5
- **`format_sse_message` は使わない**: AgentCore が yield した dict を自動的に SSE `data:` にラップするため二重フォーマット回避
- **Vite dev proxy**: AgentCore HTTP エンドポイントのCORS問題を回避。本番の API Gateway は Phase 6 以降
- **EventSource 不使用**: POST リクエスト非対応。fetch + ReadableStream でSSE手動パース
- **owner_sub をペイロードに含める**: AgentCore の JWT 検証通過後なのでペイロード内の owner_sub と s3_key プレフィックスで所有者照合

### デプロイ手順（実装後に手動実施）
1. DevContainer 内で `uv add bedrock-agentcore-starter-toolkit`
2. `cd backend && agentcore dev` でローカルテスト
3. フロントエンドから疎通確認
4. `agentcore launch` で AgentCore Runtime にデプロイ
5. Cognito JWT 認証を設定（Discovery URL + Allowed Clients）
6. エンドポイント URL を Vite proxy の target に設定

### 検証方法
1. `cd backend && agentcore dev` でエコーエージェント起動
2. `curl -X POST http://localhost:8080/invocations -H "Content-Type: application/json" -d '{"s3_key":"private/test-sub/audio/test.mp3","owner_sub":"test-sub"}' --no-buffer` でSSEイベントが段階的に返ることを確認
3. `npm run dev` で Vite 開発サーバーを起動
4. ブラウザでログイン → 音声アップロード → 「分析開始」→ 進捗表示 → モック結果表示

### PR
`feature/phase3-agentcore-echo` ブランチでPR作成

---

### Phase 3 追加修正（PR #3 レビュー対応）
- `.bedrock_agentcore.yaml`: `runtime:` 形式 → `default_agent: / agents:` 形式に修正（Starter Toolkit の正しいスキーマ）
- `useSSEChat.ts`: `owner_sub` を `idToken.payload.sub` → `session.identityId` に修正（S3 パスは identityId ベース）
- `AnalysisRunner.tsx`: s3Key 変更時のリセット、MDダウンロード、ストリーム切断検証を追加
- `backend/main.py`: summary から s3_key を分離、data に file_name/file_path を追加

---

## Phase 4: AWS Transcribe 文字起こし統合 — 完了

### Context
Phase 1-3 完了。エコーエージェント（モックSSE）がフロントエンドと疎通済み。
Phase 4 ではモック部分を実際の AWS Transcribe に置き換え、音声ファイルの文字起こしを実行する。
LLM 分析（Strands Agent）は Phase 5。

**完了条件**: アップロード済みの音声が Transcribe で文字起こしされ、結果が SSE で返り、S3 にキャッシュされる。

### アーキテクチャ
```
[ブラウザ] POST /api/analyze { s3_key, owner_sub }
  ↓
[AgentCore / agentcore dev]
  ↓
[backend/main.py]
  ├─ s3_key 検証
  ├─ yield: queued / upload
  ├─ キャッシュ確認（S3 に文字起こし済み JSON があるか）
  │   ├─ あり → JSON 読み込み、Transcribe スキップ
  │   └─ なし → Transcribe ジョブ起動 + ポーリング + 結果保存
  ├─ yield: running / transcribe（進捗メッセージ）
  ├─ yield: partial / content（文字起こしテキストのプレビュー）
  └─ yield: completed / finalize（結果 + transcript_s3_key + コスト）
```

### キャッシュパス（S3）
音声パスから決定的に導出:
```
音声:       private/{owner_sub}/audio/20260209T...Z_test.mp3
文字起こし: private/{owner_sub}/transcripts/20260209T...Z_test.mp3.json
```

### 実装手順
1. `backend/.env` — ローカル開発用環境変数（.gitignore 追加済み）
2. `backend/tools/transcribe.py` — Transcribe 呼び出し + キャッシュロジック
3. `backend/main.py` — エコーモック → Transcribe 置き換え
4. `backend/events/sse.py` — result_event に transcript パラメータ追加
5. `frontend/src/types/sse.ts` — AnalysisResultData に transcript フィールド追加
6. `frontend/src/components/analysis/AnalysisRunner.tsx` — 文字起こし折りたたみ表示

### PR
`feature/phase4-transcribe` ブランチでPR作成

---

## Phase 5: Strands Agent によるプレゼンテーション LLM 分析 — 完了

### Context
Phase 1-4 完了。音声アップロード → Transcribe 文字起こし → SSE 結果返却が動作する状態。
Phase 4 では strengths/improvements がプレースホルダ。
Phase 5 では **Strands Agents で文字起こしテキストを LLM 分析**し、実際の分析結果を返す。

**完了条件**: 文字起こしテキストが LLM で分析され、具体的な strengths/improvements/summary が SSE で返り、コスト概算が表示される。

### アーキテクチャ

```
[backend/main.py]
  ├─ Step 1: queued/upload（既存）
  ├─ Step 2: running/transcribe → transcribe_audio()（既存）
  ├─ Step 3: running/speech → "話し方を分析中…"
  │   └─ Orchestrator Agent 実行
  │       ├─ speech_analyzer tool（Haiku 4.5 サブエージェント）
  │       └─ content_analyzer tool（Haiku 4.5 サブエージェント）
  ├─ Step 4: running/content → "内容分析が完了しました"
  ├─ Step 4.5: partial/content → 分析プレビュー
  └─ Step 5: completed/finalize → 実際の分析結果 + agent_cost
```

#### Agents-as-Tools パターン
```
Orchestrator Agent（Sonnet 4.5: us.anthropic.claude-sonnet-4-5-20250929-v1:0）
  ├─ tools: [speech_analyzer, content_analyzer]
  ├─ speech_analyzer: @tool → Haiku 4.5 で話し方分析（コスト抑制）
  ├─ content_analyzer: @tool → Haiku 4.5 で内容分析（コスト抑制）
  └─ 両結果を統合し JSON で summary/strengths/improvements を出力
```

### 実装手順

#### 1. `backend/tools/cost_tracker.py` を新規作成
Strands Agent 実行後のトークン数から USD コストを算出。

- 料金テーブル: Sonnet 4.5（$3/$15 per 1M tokens）、Haiku 4.5（$0.80/$4 per 1M tokens）
- `AgentTokenUsage` dataclass: agent_name, input/output_tokens, model_id → cost_usd
- `extract_usage_from_result()`: `AgentResult.metrics.accumulated_usage` からトークン数を抽出
- `calculate_total_cost()`: 全エージェント合算 → `AgentExecutionCostSummary` を返却

#### 2. `backend/agents/speech_analyzer.py` を新規作成
`@tool` デコレータで Speech Analyzer サブエージェント（Haiku 4.5）を定義。

分析観点:
1. 話速（テキスト密度・文の長さから推定）
2. フィラー（「えー」「あの」「まあ」等の頻度）
3. 間の使い方（句読点・フレーズの切れ目から推定）
4. 言い回しの明瞭さ（曖昧表現・冗長表現の有無）

出力: `{"speech_strengths": [...], "speech_improvements": [...], "speech_summary": "..."}`

#### 3. `backend/agents/content_analyzer.py` を新規作成
`@tool` デコレータで Content Analyzer サブエージェント（Haiku 4.5）を定義。

分析観点:
1. 構成（導入-本論-結論）
2. 論理性（主張と根拠の整合性）
3. 具体性（データ・事例の使用）
4. 言葉遣い（聴衆への適切さ）
5. メッセージの明確さ

出力: `{"content_strengths": [...], "content_improvements": [...], "content_summary": "..."}`

#### 4. `backend/agents/orchestrator.py` を新規作成
Speech/Content Analyzer を tools として統合し、最終レポートを生成。

- `run_orchestrator(transcript: str) -> OrchestratorResult` を公開
- `invoke_async` で非同期実行（main.py が async generator のため）
- Orchestrator プロンプト: 「必ず両方の tool を呼び出すこと」「最終出力は JSON のみ」
- JSON パースにフォールバック（正規表現抽出）を実装
- 各エージェントのトークン使用量を個別に保持して合算

#### 5. `backend/agents/__init__.py` を新規作成
`run_orchestrator`, `OrchestratorResult` をエクスポート。

#### 6. `backend/main.py` を変更
Step 3-5 の暫定部分を Orchestrator 呼び出しに置き換え。

- Step 3（speech）: 「話し方を分析中…」→ `run_orchestrator(result.transcript)`
- Step 4（content）: 分析完了通知
- Step 5（finalize）: `orch_result.summary/strengths/improvements/cost_summary`
- エラーハンドリング: Agent 失敗時は `AGENT_ERROR` で failed イベント

#### 7. `doc/progress.md` を更新

### 対象ファイル一覧
| ファイル | 操作 |
|---|---|
| `backend/tools/cost_tracker.py` | 新規 |
| `backend/agents/__init__.py` | 新規 |
| `backend/agents/speech_analyzer.py` | 新規 |
| `backend/agents/content_analyzer.py` | 新規 |
| `backend/agents/orchestrator.py` | 新規 |
| `backend/main.py` | 変更 |
| `doc/progress.md` | 変更 |

**フロントエンド変更なし** — 既存の型定義と UI がそのまま動作する。

### 設計判断
- **Agents-as-Tools パターン**: basic_design.md の方針通り
- **モデル選択**: Orchestrator = Sonnet 4.5（統合品質重視）、サブエージェント = Haiku 4.5（コスト抑制）
- **invoke_async**: main.py が async generator なので Agent 実行も非同期
- **callback_handler=None**: 全エージェントで中間出力を抑制
- **JSON 出力 + フォールバック**: LLM が JSON 以外を返す場合に備え正規表現抽出
- **コスト計算**: 各エージェントの `metrics.accumulated_usage` を個別に保持して合算
- **文字起こしテキスト長さ制限**: 先頭 50,000 文字に切り詰め（トークン上限対策）

### 前提条件
- DevContainer で AWS 認証が有効
- IAM に `bedrock:InvokeModel` / `bedrock:InvokeModelWithResponseStream` 権限
- Bedrock で Claude Sonnet 4.5 / Haiku 4.5 のモデルアクセスが有効

### 検証方法
1. `cd backend && agentcore dev` でローカル起動
2. curl でテスト（Transcribe 済みキャッシュがある s3_key を使用）
3. 確認ポイント:
   - speech/content ステップが進行すること
   - summary が具体的な分析内容であること
   - strengths/improvements が実際の分析結果であること
   - agent_cost.total_usd > 0 であること
   - agent_cost.breakdown に orchestrator/speech_analyzer/content_analyzer が含まれること
4. フロントエンドで E2E 確認

### PR
`feature/phase5-llm-analysis` ブランチで PR 作成

---

## Phase 6: UI仕上げ — 完了

### Context
Phase 5 完了。LLM 分析結果が SSE で返るようになった。
Phase 6 では完成した Web アプリとして使える状態に仕上げた。

### 実装内容
- `index.css`: CSS 変数（--color-primary 等）・`.btn` 共通スタイルを追加
- `components/layout/Header.tsx`: タイトル・ユーザーメール・サインアウトボタン
- `App.tsx`: Header + main レイアウトに整理
- `components/result/`: SummaryCard・StrengthsList・ImprovementsList・AgentCostDisplay を新規作成
  - AgentCostDisplay: `<details>` で折りたたみ表示
- `AnalysisRunner.tsx`: result コンポーネント使用、エラー時に再試行ボタン追加、ボタン二重表示を修正
- `AnalysisRunner.css` / `AudioUploader.css`: max-width を `var(--content-width)` に統一、モバイル対応追加

### PR
`feature/phase6-ui-polish` ブランチで PR 作成

---

## Phase 7: 品質向上 & 本番準備（テスト以外）— 完了

### Context
Phase 1-6 完了。アプリは機能的に完成。Phase 7 ではテスト以外の品質向上・運用準備を実施。

### 実装内容

#### タスク1: 価格テーブル更新手順
- `backend/tools/cost_tracker.py` の `PRICING` 辞書上に料金確認先URL・更新手順ファイルへの参照コメントを追加
- `doc/pricing-update-guide.md` を新規作成: AWS Bedrock 料金ページURL、Cross-Region Inference 料金の確認方法、PRICING / PRICING_VERSION の更新手順、新モデル追加時の手順

#### タスク2: README.md 整備
- テンプレート内容を全面書き換え
- プロジェクト概要、アーキテクチャ図、前提条件、セットアップ手順、デプロイ方法、使い方、ディレクトリ構成を記載

#### タスク3: 削除機能
- `frontend/src/hooks/useFileDelete.ts` を新規作成: Amplify Storage の `remove()` を使ったファイル削除フック
- `frontend/src/components/analysis/AnalysisRunner.tsx` に「データを削除」ボタンを追加（`window.confirm()` 確認付き）
- `frontend/src/components/analysis/AnalysisRunner.css` に `.btn--danger` スタイルを追加
- `doc/s3-lifecycle-guide.md` を新規作成: S3 ライフサイクルルールの手動設定手順

#### タスク4: CloudWatch モニタリング
- `backend/logging_config.py` を新規作成: JSON 構造化ログフォーマッター + セットアップ関数
- `backend/main.py` にログ設定の初期化、リクエスト受付・完了・エラー時のメトリクスログ出力を追加
- `doc/monitoring-guide.md` を新規作成: CloudWatch Logs Insights クエリ例、ダッシュボード作成手順

### 対象ファイル一覧
| ファイル | 操作 |
|---|---|
| `backend/tools/cost_tracker.py` | 変更（コメント追加） |
| `backend/logging_config.py` | 新規 |
| `backend/main.py` | 変更（ログ設定追加） |
| `frontend/src/hooks/useFileDelete.ts` | 新規 |
| `frontend/src/components/analysis/AnalysisRunner.tsx` | 変更（削除ボタン追加） |
| `frontend/src/components/analysis/AnalysisRunner.css` | 変更（danger スタイル追加） |
| `README.md` | 変更（全面書き換え） |
| `doc/pricing-update-guide.md` | 新規 |
| `doc/s3-lifecycle-guide.md` | 新規 |
| `doc/monitoring-guide.md` | 新規 |
| `doc/progress.md` | 変更 |

### PR
`feature/phase7-quality` ブランチで PR 作成
