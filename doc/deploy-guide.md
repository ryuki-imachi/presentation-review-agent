# AWS デプロイガイド

Presentation Review Agent をゼロから AWS にデプロイするための手順書です。

## 1. 前提条件

### 必要なツール

| ツール | バージョン | 用途 |
|---|---|---|
| Node.js | 18+ | フロントエンドビルド |
| Python | 3.12+ | バックエンド実行 |
| [uv](https://docs.astral.sh/uv/) | 最新 | Python パッケージ管理 |
| AWS CLI | v2 | AWS 操作全般 |
| Docker | 最新 | バックエンドコンテナビルド |

### AWS アカウントの準備

- **リージョン**: `us-east-1`（バージニア北部）を使用
- AWS CLI で認証を完了しておく:

```bash
aws login
# ブラウザが開くのでログイン操作を行う
```

認証後、以下で接続を確認:

```bash
aws sts get-caller-identity
```

## 2. AWS 側の事前準備

### Bedrock モデルアクセスについて

2025年9月以降、Bedrock のサーバーレスモデルは全 AWS アカウントで自動的に有効化されるようになりました。**手動でのモデルアクセス有効化は不要です。**

本アプリが使用するモデル:
- **Claude Sonnet 4.5**（Orchestrator エージェント）
- **Claude Haiku 4.5**（Speech/Content Analyzer サブエージェント）

> **Note**: IAM ポリシーや SCP でモデルアクセスを制限している場合は、`bedrock:InvokeModel` の許可が必要です。IAM ロールの事前作成は不要です（AgentCore が自動作成します）。

## 3. フロントエンドのデプロイ（Amplify Gen2）

フロントエンドは AWS Amplify Hosting を使い、GitHub リポジトリと接続して自動デプロイします。

### 3.1 Amplify Hosting で GitHub リポジトリを接続

1. [AWS コンソール](https://console.aws.amazon.com/amplify/) → AWS Amplify → **新しいアプリを作成**
2. **GitHub** を選択し、リポジトリへのアクセスを承認
3. 対象リポジトリ（`presentation-review-agent`）と `main` ブランチを選択
4. フレームワークが自動検出される（Vite + React）
5. アプリのルートディレクトリに `frontend` を指定
6. ビルド設定を確認:
   - ビルドコマンド: `npm run build`
   - 出力ディレクトリ: `dist`
7. 「保存してデプロイ」をクリック

### 3.2 Cognito + S3 の自動プロビジョニング

Amplify Gen2 は `frontend/amplify/` 配下のリソース定義を読み取り、以下を自動でプロビジョニングします:

- **Cognito User Pool**（メールログイン）— `amplify/auth/resource.ts`
- **S3 バケット**（`private/{entity_id}/*` アクセス制御）— `amplify/storage/resource.ts`

デプロイ完了後、Amplify コンソールの「デプロイされたバックエンドリソース」からそれぞれの情報を確認できます。

### 3.3 `amplify_outputs.json` について

- Amplify のデプロイプロセスがビルド時に `amplify_outputs.json` を自動生成します
- このファイルには Cognito・S3 の設定情報が含まれ、フロントエンドが実行時に読み込みます
- **手動作成は不要** — Amplify Hosting が自動で処理します
- ローカル開発時は `npx ampx sandbox` が生成します

### 3.4 デプロイ後の確認

- Amplify コンソールでデプロイステータスが「成功」になっていることを確認
- 提供された URL にアクセスし、Cognito ログイン画面が表示されることを確認
- Cognito User Pool ID と S3 バケット名をメモしておく（バックエンド設定で使用）

#### S3 バケット名の確認方法

以下のいずれかの方法で確認できます:

- **Amplify コンソール** → アプリ → 「デプロイされたバックエンドリソース」→ Storage
- **AWS コンソール** → S3 → `amplify-` で始まるバケット名を探す（`presentationaudiostorage` を含むもの）

## 4. バックエンドのデプロイ（AgentCore）

### 4.1 依存関係のインストール

プロジェクトルートで:

```bash
uv sync
```

### 4.2 環境変数の設定

`backend/.env` を作成し、S3 バケット名を設定します:

`backend/.env` を新規作成:

```env
S3_BUCKET_NAME=<Amplifyが作成したS3バケット名>
AWS_REGION=us-east-1
```

> `S3_BUCKET_NAME` には手順 3.4 で確認した S3 バケット名を設定してください。

### 4.3 ローカルでの動作確認（任意）

本番デプロイ前にローカルで動作確認したい場合:

```bash
cd backend
agentcore dev
```

別ターミナルで疎通確認:

```bash
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"s3_key":"private/test-sub/audio/test.mp3","owner_sub":"test-sub"}' \
  --no-buffer
```

### 4.4 AgentCore へのデプロイ

```bash
cd backend
agentcore launch
```

`agentcore launch` は以下を自動で行います:

1. **Dockerfile の自動生成**（プロジェクトに含まれていない場合）
2. **Docker イメージのビルド**
3. **ECR リポジトリの作成**（存在しない場合）
4. **ECR へのイメージプッシュ**
5. **IAM 実行ロールの自動作成**（`.bedrock_agentcore.yaml` で `execution_role_auto_create: true`）
6. **AgentCore Runtime へのデプロイ**

デプロイ完了後、AgentCore エンドポイント URL が表示されます。この URL をメモしておいてください。

> **Note**: 初回デプロイには数分かかることがあります。Docker イメージのビルドと ECR プッシュが主な所要時間です。

## 5. デプロイ後の設定

### 5.1 AgentCore エンドポイントに Cognito JWT 認証を設定

AgentCore エンドポイントを外部から保護するため、Cognito JWT 認証を設定します。

1. **AgentCore コンソール**でデプロイしたエージェントを選択
2. **認証設定**（Authentication）を開く
3. 以下を設定:

| 設定項目 | 値 |
|---|---|
| **Discovery URL** | `https://cognito-idp.us-east-1.amazonaws.com/<User Pool ID>/.well-known/openid-configuration` |
| **Allowed Clients** | Amplify が作成した Cognito App Client ID |

- **User Pool ID**: Amplify コンソール → アプリ → デプロイされたバックエンドリソース → Auth で確認
- **App Client ID**: Cognito コンソール → User Pool → アプリケーションの統合 → アプリクライアントで確認

### 5.2 フロントエンドからの接続設定

フロントエンドが AgentCore エンドポイントにリクエストを送れるよう設定します。

開発環境では `vite.config.ts` の proxy 設定で AgentCore エンドポイントを指定します:

```typescript
// frontend/vite.config.ts
proxy: {
  '/api/analyze': {
    target: '<AgentCore エンドポイント URL>',
    changeOrigin: true,
    rewrite: () => '/invocations',
  },
},
```

本番環境（Amplify Hosting）では、フロントエンドの SSE 通信フック（`useSSEChat.ts`）が AgentCore エンドポイントに直接リクエストを送ります。環境変数や設定ファイルで本番用エンドポイント URL を設定してください。

## 6. 動作確認

すべてのデプロイが完了したら、以下の手順で E2E 動作確認を行います:

1. **ブラウザでアクセス** — Amplify が提供する URL を開く
2. **ユーザー登録・ログイン** — メールアドレスで Cognito にサインアップ → 確認コード入力 → ログイン
3. **音声ファイルをアップロード** — mp3, wav, m4a, ogg, webm いずれかのファイルをドラッグ&ドロップまたはファイル選択
4. **「分析開始」をクリック** — 以下の進捗がリアルタイムで表示される:
   - ファイル受付
   - 音声文字起こし中（AWS Transcribe）
   - 話し方分析中（Speech Analyzer）
   - 内容分析（Content Analyzer）
5. **分析結果を確認** — サマリー・良い点・改善点・推定コストが表示される
6. **レポートダウンロード** — Markdown 形式でダウンロード可能

### トラブルシューティング

| 症状 | 確認ポイント |
|---|---|
| ログイン画面が表示されない | Amplify デプロイが成功しているか確認。`amplify_outputs.json` が生成されているか |
| アップロード失敗 | S3 バケットのアクセス制御設定を確認。Cognito Identity Pool の IAM ロールを確認 |
| 「分析開始」でエラー | AgentCore エンドポイントの JWT 認証設定を確認。Discovery URL と Allowed Clients が正しいか |
| 文字起こしエラー | Transcribe の権限（`transcribe:StartTranscriptionJob` 等）が IAM ロールにあるか確認 |
| LLM 分析エラー | Bedrock モデルアクセスが有効か確認。`bedrock:InvokeModel` 権限があるか確認 |

## 7. 運用関連

デプロイ後の運用に関する詳細は以下のガイドを参照してください:

- **[CloudWatch モニタリングガイド](monitoring-guide.md)** — ログ検索クエリ、ダッシュボード作成手順
- **[S3 ライフサイクル設定ガイド](s3-lifecycle-guide.md)** — 古いファイルの自動削除設定
- **[料金テーブル更新ガイド](pricing-update-guide.md)** — Bedrock モデル料金の更新手順
