# AWS デプロイガイド

Presentation Review Agent をゼロから AWS にデプロイするための手順書です。

Amplify Gen2 + CDK により、フロントエンド・認証・ストレージ・バックエンド（AgentCore）を一括でデプロイします。

## 1. 前提条件

### 必要なツール

| ツール | バージョン | 用途 |
|---|---|---|
| Node.js | 18+ | フロントエンドビルド・CDK デプロイ |
| npm | 10+ | パッケージ管理 |
| Docker | 最新 | AgentCore コンテナイメージのビルド |
| AWS CLI | v2 | AWS 操作全般 |

> **Note**: Python や uv はローカル開発環境では不要です。Python コードは Docker コンテナ内で実行されます。

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

### Bedrock モデルアクセスについて

2025年9月以降、Bedrock のサーバーレスモデルは全 AWS アカウントで自動的に有効化されるようになりました。**手動でのモデルアクセス有効化は不要です。**

本アプリが使用するモデル:
- **Claude Sonnet 4.5**（Orchestrator エージェント）
- **Claude Haiku 4.5**（Speech/Content Analyzer サブエージェント）

> **Note**: IAM ポリシーや SCP でモデルアクセスを制限している場合は、`bedrock:InvokeModel` の許可が必要です。IAM ロールは CDK が自動作成します。

## 2. デプロイアーキテクチャ

CDK 移行後、すべてのインフラは `frontend/amplify/` 配下の CDK コードで管理されます。

```
frontend/amplify/
├── backend.ts              ← Amplify バックエンド統合（auth + storage + agent）
├── auth/resource.ts        ← Cognito User Pool（メールログイン）
├── storage/resource.ts     ← S3 バケット（音声ファイル保存）
└── agent/
    ├── resource.ts         ← AgentCore Runtime CDK 定義
    └── runtime/            ← Python コード + Dockerfile（コンテナイメージ）
```

`npx ampx sandbox`（開発）または Amplify Hosting（本番）で以下が一括デプロイされます:

- **Cognito User Pool** — メールベースの認証
- **S3 バケット** — `private/{entity_id}/*` のアクセス制御付き
- **AgentCore Runtime** — Cognito JWT 認証付き、IAM ポリシー自動設定

## 3. ローカル開発環境のセットアップ

### 3.1 依存関係のインストール

```bash
cd frontend
npm install
```

### 3.2 Amplify Sandbox の起動

Sandbox は個人用の開発環境をクラウド上にプロビジョニングします:

```bash
cd frontend
npx ampx sandbox
```

初回は以下が自動作成されます:
- Cognito User Pool + App Client
- S3 バケット
- AgentCore Runtime（Docker イメージのビルド → ECR プッシュ → Runtime デプロイ）

> **Note**: 初回は Docker イメージのビルドと ECR プッシュがあるため、数分かかります。

デプロイ完了後、`frontend/amplify_outputs.json` が自動生成されます。このファイルにはフロントエンドが必要とする全設定（Cognito、S3、AgentCore Runtime ARN）が含まれます。

### 3.3 フロントエンド開発サーバーの起動

別ターミナルで:

```bash
cd frontend
npm run dev
```

`http://localhost:5173` でアクセスできます。

### 3.4 Sandbox の停止

開発が終わったら Sandbox を停止します（`Ctrl+C` または以下のコマンド）:

```bash
cd frontend
npx ampx sandbox delete
```

> **Note**: `sandbox delete` で AWS リソースが削除されます。`amplify_outputs.json` はローカルに残るため、次回 `npx ampx sandbox` で再作成されます。

## 4. 本番環境のデプロイ（Amplify Hosting）

本番環境は AWS Amplify Hosting を使い、GitHub リポジトリと接続して自動デプロイします。

### 4.1 事前準備: CDK Bootstrap

アカウント × リージョンごとに1回だけ、CDK ブートストラップが必要です。AWS CloudShell（対象アカウント、us-east-1 リージョン）で実行:

```bash
npx cdk bootstrap aws://<アカウントID>/us-east-1
```

### 4.2 Amplify Hosting で GitHub リポジトリを接続

1. [AWS コンソール](https://console.aws.amazon.com/amplify/) → AWS Amplify → **新しいアプリを作成**
2. **GitHub** を選択し、リポジトリへのアクセスを承認
3. 対象リポジトリ（`presentation-review-agent`）と `main` ブランチを選択
4. **「モノレポ」にチェック**を入れ、アプリのルートディレクトリに **`frontend`** を指定
5. サービスロールが設定されていることを確認（`AmplifyBackendDeployFullAccess` ポリシーが必要）
6. 「保存してデプロイ」をクリック

> **Note**: モノレポ選択時にサービスロール作成がスキップされる場合があります。「全般設定」でサービスロールが空欄なら、IAM で `AmplifyBackendDeployFullAccess` ポリシーを付けたロール（信頼関係: `amplify.amazonaws.com`）を作成し、設定してください。

### 4.3 amplify.yml によるビルド設定

リポジトリルートの `amplify.yml` で、バックエンドとフロントエンドのビルドを制御しています:

```yaml
version: 1
applications:
  - appRoot: frontend
    backend:
      phases:
        preBuild:
          commands:
            - npm ci
        build:
          commands:
            - npx ampx pipeline-deploy --branch $AWS_BRANCH --app-id $AWS_APP_ID
    frontend:
      phases:
        preBuild:
          commands:
            - npm ci
        build:
          commands:
            - npx ampx generate outputs --branch $AWS_BRANCH --app-id $AWS_APP_ID
            - npm run build
      artifacts:
        baseDirectory: dist
        files:
          - "**/*"
```

- **backend フェーズ**: `ampx pipeline-deploy` で Cognito / S3 / AgentCore を CloudFormation 経由でデプロイ
- **frontend フェーズ**: `ampx generate outputs` で `amplify_outputs.json` を生成した後、Vite ビルドを実行

### 4.4 デプロイされるリソース

`ampx pipeline-deploy` により以下が自動プロビジョニングされます:

- **Cognito User Pool**（メールログイン）— `amplify/auth/resource.ts`
- **S3 バケット**（`private/{entity_id}/*` アクセス制御）— `amplify/storage/resource.ts`
- **AgentCore Runtime**（JWT 認証 + IAM ポリシー付き）— `amplify/agent/resource.ts`

CDK により以下も自動設定されます:
- AgentCore ↔ Cognito の JWT 認証連携
- AgentCore → S3 / Bedrock / Transcribe の IAM ポリシー

### 4.5 デプロイ後の確認

- Amplify コンソールでデプロイステータスが「成功」になっていることを確認
- 提供された URL にアクセスし、Cognito ログイン画面が表示されることを確認

## 5. フロントエンドと AgentCore の接続

CDK 移行後、フロントエンドは `amplify_outputs.json` の `custom.agentRuntimeArn` から AgentCore エンドポイント URL を自動構築します。**手動での URL 設定やプロキシ設定は不要です。**

```typescript
// useSSEChat.ts での URL 構築（自動）
const runtimeArn = outputs.custom.agentRuntimeArn;
const region = runtimeArn.split(":")[3];
const encodedArn = encodeURIComponent(runtimeArn);
const url = `https://bedrock-agentcore.${region}.amazonaws.com/runtimes/${encodedArn}/invocations?qualifier=DEFAULT`;
```

認証には Cognito の `accessToken` を Bearer トークンとして使用します。

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
| 「分析開始」でエラー | AgentCore Runtime がデプロイ済みか確認。`amplify_outputs.json` に `agentRuntimeArn` があるか |
| 文字起こしエラー | AgentCore の IAM ロールに `transcribe:StartTranscriptionJob` 権限があるか確認（CDK で自動付与済み） |
| LLM 分析エラー | Bedrock モデルアクセスが有効か確認。AgentCore の IAM ロールに `bedrock:InvokeModel` 権限があるか確認（CDK で自動付与済み） |
| Sandbox デプロイが遅い | Docker イメージのビルドが主な所要時間。初回は特に時間がかかる |

## 7. 運用関連

デプロイ後の運用に関する詳細は以下のガイドを参照してください:

- **[CloudWatch モニタリングガイド](monitoring-guide.md)** — ログ検索クエリ、ダッシュボード作成手順
- **[S3 ライフサイクル設定ガイド](s3-lifecycle-guide.md)** — 古いファイルの自動削除設定
- **[料金テーブル更新ガイド](pricing-update-guide.md)** — Bedrock モデル料金の更新手順

## 参考: 旧手動デプロイ（非推奨）

CDK 移行前の手動デプロイ手順は `backend/` ディレクトリに残されています。`agentcore launch` による手動デプロイはフォールバック用として利用可能ですが、通常は CDK 管理の手順を推奨します。詳細は [CDK 移行ガイド](cdk-migration.md) を参照してください。
