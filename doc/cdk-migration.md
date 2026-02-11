# Bedrock AgentCore CDK 移行ガイド

## 背景と目的

バックエンドの AgentCore Runtime は `agentcore launch` コマンドで手動デプロイしており、IAM ロールや JWT 認証の設定も手動で行っていた。これを Amplify Gen2 の CDK に統合し、`npx ampx sandbox` や Amplify Hosting の CI/CD で再現可能なデプロイを実現する。

## Before / After

### Before（手動デプロイ）
- `backend/` ディレクトリで `agentcore launch` を実行
- IAM ロール・JWT 認証を手動設定
- 環境変数（S3_BUCKET_NAME 等）を `.env` や手動で設定
- Runtime 名: `presentation-review-agent`

### After（CDK 管理）
- `frontend/amplify/agent/` に CDK リソース定義と Python コードを配置
- `npx ampx sandbox` で auth / storage / agent を一括デプロイ
- Cognito・S3 との連携が CDK 内で自動解決
- Runtime 名: `presentation_review_agent`（CDK 管理用に別名）

## ディレクトリ構成

```
frontend/amplify/
├── backend.ts              ← AgentCore Runtime を追加
├── auth/resource.ts        ← 変更なし
├── storage/resource.ts     ← 変更なし
└── agent/
    ├── resource.ts         ← AgentCore Runtime CDK 定義
    └── runtime/            ← backend/ から Python コードをコピー
        ├── Dockerfile
        ├── main.py
        ├── logging_config.py
        ├── requirements.txt
        ├── agents/
        ├── tools/
        └── events/
```

## 使用する CDK パッケージ

| パッケージ | 用途 |
|---|---|
| `@aws-cdk/aws-bedrock-agentcore-alpha` | AgentCore Runtime CDK コンストラクト |
| `aws-cdk-lib` | IAM, ECR Assets 等の基盤 CDK |
| `constructs` | CDK コンストラクトベース |

## 段階的な移行手順

1. **依存パッケージ追加**: `npm install` で CDK パッケージを追加
2. **Python コードコピー**: `backend/` → `frontend/amplify/agent/runtime/`
3. **Dockerfile 作成**: コンテナイメージのビルド定義
4. **CDK リソース定義**: `agent/resource.ts` で Runtime を定義
5. **backend.ts 更新**: AgentCore を Amplify バックエンドに統合
6. **Sandbox デプロイ**: `npx ampx sandbox` で動作確認
7. **E2E 確認**: フロントエンドからの疎通テスト

## 手動デプロイリソースとの共存

- CDK 管理の Runtime 名は `presentation_review_agent`（アンダースコア区切り）
- 手動デプロイの Runtime 名は `presentation-review-agent`（ハイフン区切り）
- 両者は別リソースとして共存可能
- CDK 版での動作確認が完了したら、手動デプロイ版を `agentcore delete` で削除

## 注意点

- **ARM64**: AgentCore Runtime は ARM64 コンテナ前提。Mac (Apple Silicon) ならネイティブビルド可能
- **alpha パッケージ**: `@aws-cdk/aws-bedrock-agentcore-alpha` は破壊的変更の可能性あり
- **バージョン互換**: `aws-cdk-lib` のバージョンを AgentCore alpha と合わせる必要がある
- **sandbox vs 本番**: sandbox はローカルビルド、本番は CodeBuild によるビルドを検討
- **`backend/` ディレクトリ**: 移行完了まで残し、フォールバックとして使用可能
