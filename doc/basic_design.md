# presentation-review-agent 設計プラン

## Context

参考リポジトリ `prezentation-feedback-agent`（Streamlit + ローカル実行）を改良し、**AWS Amplify Gen2 + Bedrock AgentCore Runtime** を使ったモダンなサーバーレスWebアプリとして再構築する。プレゼンテーション音声を分析し、話し方・内容について多角的なフィードバックを提供するマルチエージェントシステム。

## 前提条件

- 現時点の運用は単一ユーザー（個人利用）
- 将来の複数ユーザー利用に備え、`cognito_sub` 単位でデータ分離できる構造にする
- 分析結果は可能な限りストリーミングで逐次表示する
- 1回の分析実行ごとに Strandsエージェント実行料金（概算USD）を結果画面に表示する
- 音声データ保持に厳密な運用ルールは設けない（任意削除は可能にする）

## 現在の状況（2026-02-08）

### 合意済み事項
- 現在は個人利用を前提に進める
- 将来の複数ユーザー対応のため、`cognito_sub` ベースのデータ分離を維持する
- 解析結果はSSEでストリーミング表示する
- 結果画面には Strandsエージェント実行料金（概算）を表示する
- 料金表示対象はエージェント実行分のみ（Transcribe/S3等は対象外）

### このリポジトリで作成済みの実装雛形
- `/Users/ryuki/Desktop/work/presentation-review-agent/frontend/src/types/sse.ts`
  - SSEイベント型（`analysis.status/partial/result`）
  - `analysis.result.data.agent_cost` の型定義と型ガード
- `/Users/ryuki/Desktop/work/presentation-review-agent/frontend/src/types/index.ts`
  - 型の再エクスポート
- `/Users/ryuki/Desktop/work/presentation-review-agent/backend/events/sse.py`
  - SSEイベント生成関数
  - `AgentExecutionCostSummary`
  - `new_analysis_result_event`（`agent_cost` 付き）
  - 所有者照合ヘルパー（`request_sub` と `owner_sub` の一致確認）
- `/Users/ryuki/Desktop/work/presentation-review-agent/backend/events/__init__.py`
  - 上記ヘルパーの再エクスポート

### まだ未実装の項目
- `frontend/` の実アプリ本体（Vite/Amplify/Auth/UIコンポーネント）
- `backend/main.py` のAgentCoreエントリーポイント
- `backend/tools/cost_tracker.py` の料金算出ロジック
- `run_id + owner_sub` の実行状態永続化
- SSE再接続（`Last-Event-ID`）の実運用実装

### 直近の実装順
1. `backend/main.py` で `run_id` 発行とSSE送信ループを実装
2. `backend/tools/cost_tracker.py` で Strands実行料金の概算算出を実装
3. `frontend/src/hooks/useSSEChat.ts` で受信/再接続/描画を実装
4. 結果UIに `agent_cost.total_usd` と `agent_cost.breakdown` を表示

## 全体アーキテクチャ

```
[ブラウザ (React + Vite)]
       |
       |-- Cognito認証 (JWT)
       |-- S3アップロード (Amplify Storage)
       |-- AgentCore Runtime 呼び出し (SSE)
       |
       v
[Bedrock AgentCore Runtime (Docker/ECR)]
       |
       |-- Orchestrator Agent (Claude Sonnet)
       |     |-- Speech Analyzer Agent (話し方分析)
       |     |-- Content Analyzer Agent (内容分析)
       |
       |-- AWS Transcribe (音声書き起こし)
       |-- S3 (音声ファイル & 書き起こし結果)
       v
[フィードバックレポート → SSEでブラウザに返却]
```

### データフロー
1. ユーザーがCognitoログイン
2. 音声ファイルをAmplify Storage (S3) にアップロード（`private/{cognito_sub}/` 配下）
3. フロントエンドがAgentCore Runtimeを呼び出し、`run_id` を受け取る（JWT認証 + SSE）
4. Orchestrator が Transcribe ジョブを起動し、進捗イベントをSSEで通知
5. Transcribe完了後に Speech Analyzer + Content Analyzer を実行し、統合レポートを段階的にSSE送信
6. `cost_tracker` が Strandsエージェント実行料金（Bedrockモデル利用分）を算出し、最終結果に付与
7. フロントエンドは `run_id` を保持し、SSE切断時は再接続して進捗を復元

### 将来の複数ユーザー対応余地（マルチテナント最小要件）
- S3の保存先は常に `private/{cognito_sub}/...` とし、他プレフィックスは扱わない
- バックエンドはJWTから `cognito_sub` を抽出し、受け取った `s3_key` の所有者と一致しない場合は拒否する
- `run_id` は推測困難なID（UUID）を採用し、サーバー側状態に `owner_sub` を必ず保存する
- 進捗取得・再接続・結果取得のすべてで `run_id` と `owner_sub` の一致を検証する

## ディレクトリ構成

```
presentation-review-agent/
├── .devcontainer/              # 既存
├── frontend/                   # React + Vite + Amplify Gen2
│   ├── amplify/
│   │   ├── auth/resource.ts          # Cognito認証
│   │   ├── storage/resource.ts       # S3ストレージ
│   │   └── backend.ts                # Amplifyバックエンド統合
│   ├── src/
│   │   ├── components/
│   │   │   ├── layout/               # Header, Layout
│   │   │   ├── upload/               # AudioUploader, FileDropZone
│   │   │   ├── analysis/             # Progress, Result, Summary, Strengths, Improvements
│   │   │   └── common/               # Button, Card
│   │   ├── hooks/
│   │   │   ├── useSSEChat.ts         # AgentCore SSE通信
│   │   │   └── useAudioUpload.ts     # S3アップロード
│   │   ├── types/index.ts
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   └── vite.config.ts
├── backend/                    # Python (AgentCore用)
│   ├── agents/
│   │   ├── orchestrator.py           # 統括エージェント
│   │   ├── speech_analyzer.py        # 話し方分析
│   │   └── content_analyzer.py       # 内容分析
│   ├── tools/
│   │   ├── transcribe.py             # AWS Transcribe連携
│   │   ├── s3_utils.py               # S3操作
│   │   └── cost_tracker.py           # コスト追跡
│   ├── prompts/                      # システムプロンプト
│   ├── main.py                       # AgentCoreエントリーポイント
│   ├── Dockerfile                    # ARM64コンテナ
│   └── pyproject.toml
├── scripts/                    # デプロイスクリプト
├── doc/                        # 設計ドキュメント
├── pyproject.toml              # ルート(既存)
└── README.md
```

## 開発フェーズ

### Phase 1: 基盤構築（React + Cognito認証）
- `frontend/` に React + Vite プロジェクト初期化
- Amplify Gen2 初期化（`npx ampx init`）
- Cognito認証設定（`amplify/auth/resource.ts`）
- `<Authenticator>` コンポーネントでログイン/ログアウト実装
- `npx ampx sandbox` でローカルテスト
- **完了条件**: ブラウザでログイン/ログアウトができる

### Phase 2: ストレージ & 音声アップロード
- Amplify Storage設定（`amplify/storage/resource.ts`）
- `AudioUploader` コンポーネント（ファイル選択 + ドラッグ&ドロップ）
- `uploadData` によるS3アップロード + 進捗表示
- 保存先キーを `private/{cognito_sub}/audio/{timestamp}_{filename}` に統一
- **完了条件**: 音声ファイルがS3に保存される

### Phase 3: バックエンド最小構成（AgentCore デプロイ）
- `backend/main.py` に BedrockAgentCoreApp + エコーエージェント
- ARM64 Docker ビルド → ECRプッシュ
- AgentCore Runtime デプロイ（Starter Toolkit使用）
- Cognito JWT認証の設定
- JWTから `sub` を取り出し、`s3_key` / `run_id` 所有者照合を行う認可ガードを追加
- `useSSEChat` フックでフロントエンドからの疎通テスト
- `run_id` ベースのSSEイベントフォーマットを定義（`queued/running/partial/completed/failed`）
- **完了条件**: フロントエンドからAgentCoreにメッセージを送り、SSEで逐次応答が返る

### Phase 4: 音声書き起こし統合
- `tools/transcribe.py` に `@tool` デコレータ付きTranscribeツール
- Orchestrator Agent がS3パスを受け取りTranscribeジョブを起動・監視するフロー
- ジョブ状態を `run_id` + `owner_sub` 単位で保持（再接続時の復元に使用）
- フロントエンドの進捗ステップ表示（キュー投入/書き起こし中/完了）
- **完了条件**: 音声アップロード後、進捗がストリーミング表示され、最終的に書き起こしテキストが表示される

### Phase 5: 分析エージェント実装
- Speech Analyzer Agent（話速・フィラー・間の分析）
- Content Analyzer Agent（構成・論理性・言葉遣いの分析）
- Orchestrator Agent 完成（統合サマリ生成）
- `cost_tracker.py` で Strandsエージェント実行料金を推定し、`analysis.result` に含める
- Agents-as-Tools パターンで実装
- **完了条件**: 多角的な分析結果が表示される

### Phase 6: UI仕上げ
- SummaryCard, StrengthsList, ImprovementsList コンポーネント
- エージェント実行料金表示コンポーネント（総額 + エージェント別内訳）
- レスポンシブ対応
- エラーハンドリングUI
- SSE切断時の再接続UI（再試行ボタン、自動再接続、失敗時メッセージ）
- **完了条件**: 完成したWebアプリとして使える

### Phase 7: 品質向上 & 本番準備
- テスト追加（pytest + Vitest）
- 価格テーブル更新手順の整備（モデル価格改定時に更新）
- CloudWatchモニタリング
- 任意削除機能（アップロード済み音声/書き起こし結果の手動削除）
- README.md整備

## 運用方針（個人利用）

- データ保持期間は固定せず、ユーザーが必要な期間だけ保持する
- 誤操作対策として、削除機能は明示的な確認ダイアログを出す
- コスト抑制のため、将来的にS3ライフサイクルルール（例: 30日後削除）を任意で設定可能にする
- エージェント実行料金表示は請求確定値ではなく概算値として表示する（見積もり用途）

## 主要な技術選択

| 項目 | 選択 | 理由 |
|---|---|---|
| フロントエンド | React + Vite + TypeScript | Amplify Gen2の標準構成 |
| 認証 | Cognito (Amplify Auth) | AgentCoreのJWT認証と統合可能 |
| ストレージ | Amplify Storage (S3) | Transcribeとの連携がスムーズ |
| バックエンド | AgentCore Runtime | サーバーレス、維持費が安い |
| エージェントFW | Strands Agents | 参考リポジトリと同じ、Agents-as-Toolsパターン |
| LLMモデル | Claude Sonnet 4.5 | 高品質な分析結果 |
| デプロイ | Starter Toolkit | 最もシンプルなAgentCoreデプロイ方法 |
| リージョン | us-east-1 | AgentCore対応リージョン |

## SSEイベント仕様（`run_id` ベース）

### 目的
- 長時間処理（Transcribe + 分析）の進捗を段階的にUI表示する
- SSE切断後も同一 `run_id` の実行状態を復元する
- 将来の複数ユーザー利用でも `owner_sub` で参照制御できるようにする

### 共通フィールド

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `run_id` | string (UUID) | Yes | 分析実行単位のID |
| `owner_sub` | string | Yes | JWT由来の `cognito_sub` |
| `status` | string | Yes | `queued/running/partial/completed/failed` |
| `step` | string | Yes | `upload/transcribe/speech/content/finalize` |
| `emitted_at` | string (ISO8601) | Yes | サーバー側イベント発行時刻 |
| `message` | string | No | 画面表示向けメッセージ |
| `data` | object | No | ステップ固有データ |
| `error` | object | No | 失敗時の詳細（`code`,`detail`） |

### ステータス遷移

`queued` → `running` → `partial`（0回以上）→ `completed`  
`queued/running/partial` のいずれかから `failed` に遷移可能

### イベント名
- `analysis.status`: キュー投入、実行開始、完了、失敗などの状態通知
- `analysis.partial`: 中間成果（書き起こし途中、分析途中サマリ）
- `analysis.result`: 最終結果（サマリ・よかった点・改善点・Strands実行料金）

### `analysis.result.data` 必須項目
- `summary`: string
- `strengths`: string[]
- `improvements`: string[]
- `agent_cost`: object
  - `total_usd`: number
  - `breakdown`: object（例: `orchestrator_usd`, `speech_analyzer_usd`, `content_analyzer_usd`）
  - `is_estimated`: boolean
  - `pricing_version`: string
- `agent_cost` は Strandsエージェント実行料金のみを対象とし、Transcribe/S3等の周辺サービス費用は含めない

### 再接続ルール
- クライアントは `run_id` をローカル保持して再接続時に送信する
- サーバーは `run_id` と `owner_sub` が一致しない場合は `403` で拒否
- `Last-Event-ID` がある場合は未受信イベントのみ再送し、ない場合は最新状態を1件返して継続配信する
- `completed` または `failed` を受信したらストリームを正常終了する

### ペイロード例

```json
{
  "event": "analysis.status",
  "id": "evt_0001",
  "run_id": "8a6f6d7d-5c9a-4b14-9e8b-f4a4e5f1d5ad",
  "owner_sub": "9d1f...c3",
  "status": "running",
  "step": "transcribe",
  "emitted_at": "2026-02-08T10:15:30Z",
  "message": "音声を書き起こししています"
}
```

```json
{
  "event": "analysis.partial",
  "id": "evt_0007",
  "run_id": "8a6f6d7d-5c9a-4b14-9e8b-f4a4e5f1d5ad",
  "owner_sub": "9d1f...c3",
  "status": "partial",
  "step": "content",
  "emitted_at": "2026-02-08T10:16:22Z",
  "data": {
    "partial_summary": "導入は明確。結論への接続を強化するとさらに良い。"
  }
}
```

```json
{
  "event": "analysis.result",
  "id": "evt_0012",
  "run_id": "8a6f6d7d-5c9a-4b14-9e8b-f4a4e5f1d5ad",
  "owner_sub": "9d1f...c3",
  "status": "completed",
  "step": "finalize",
  "emitted_at": "2026-02-08T10:17:03Z",
  "data": {
    "summary": "全体として論旨は明確。",
    "strengths": ["導入が分かりやすい", "根拠の提示が具体的"],
    "improvements": ["結論を先に述べる", "間を少し短くする"],
    "agent_cost": {
      "total_usd": 0.0178,
      "breakdown": {
        "orchestrator_usd": 0.0064,
        "speech_analyzer_usd": 0.0057,
        "content_analyzer_usd": 0.0057
      },
      "is_estimated": true,
      "pricing_version": "2026-02-08"
    }
  }
}
```

## 検証方法

1. **Phase 1**: ブラウザでサインアップ → ログイン → ログアウト
2. **Phase 2**: 音声ファイルをアップロード → S3コンソールで確認
3. **Phase 3**: フロントエンドからメッセージ送信 → AgentCoreからSSEで段階的応答
4. **Phase 4**: 音声アップロード → 進捗表示（キュー投入/書き起こし中）→ 書き起こしテキスト表示
5. **Phase 5**: 音声アップロード → サマリ・よかった点・改善点・Strands実行料金が表示
6. **Phase 6-7**: SSE切断時の再接続復帰、E2Eテスト、モバイル表示確認
7. **将来拡張テスト**: 別ユーザーの `s3_key` / `run_id` を指定した場合に拒否（認可ガード確認）
